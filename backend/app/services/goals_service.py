"""Authenticated profile-scoped goal and milestone operations."""
from datetime import date, datetime, timezone
import uuid

from .goals_store import GoalStorageUnavailable, GoalsStore
from .ownership_store import OwnershipNotFound, OwnershipUnavailable


class GoalNotFound(Exception):
    pass


class GoalConflict(Exception):
    pass


def _stamp(value):
    return value.isoformat()


def _plain(row):
    return dict(row) if row is not None else None


def _goal_id(value):
    try:
        parsed = uuid.UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


class GoalsService:
    def __init__(self, profiles, store=None, clock=None):
        self.profiles = profiles
        self.store = store or GoalsStore()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _authorize(self, identity, profile_id):
        try:
            self.profiles.get(identity, profile_id)
        except OwnershipNotFound:
            raise
        except OwnershipUnavailable:
            raise

    def authorize_profile(self, identity, profile_id):
        self._authorize(identity, profile_id)

    def _ensure_profile(self, connection, identity, profile_id):
        now = _stamp(self.clock())
        connection.execute('INSERT INTO goal_profiles(profile_id,account_id,created_at) VALUES (?,?,?) '
                           'ON CONFLICT(profile_id,account_id) DO NOTHING',
                           (profile_id, identity.account_id, now))
        row = connection.execute('SELECT account_id FROM goal_profiles WHERE profile_id=?',
                                  (profile_id,)).fetchone()
        if not row or row['account_id'] != identity.account_id:
            raise GoalConflict('This profile is not available for goal storage.')

    @staticmethod
    def _milestones(connection, goal_id, profile_id, account_id):
        rows = connection.execute('SELECT * FROM milestones WHERE goal_id=? AND profile_id=? AND account_id=? '
                                  'ORDER BY CASE WHEN target_date IS NULL THEN 1 ELSE 0 END,target_date,created_at,milestone_id',
                                  (goal_id, profile_id, account_id)).fetchall()
        return [_plain(row) for row in rows]

    def _goal(self, connection, identity, profile_id, goal_id):
        row = connection.execute('SELECT * FROM goals WHERE goal_id=? AND profile_id=? AND account_id=?',
                                 (goal_id, profile_id, identity.account_id)).fetchone()
        if not row:
            raise GoalNotFound()
        goal = _plain(row)
        goal['milestones'] = self._milestones(connection, goal_id, profile_id, identity.account_id)
        return goal

    def _serialize_goal(self, goal, today):
        milestones = goal['milestones']
        total = len(milestones)
        completed = sum(milestone['status'] == 'completed' for milestone in milestones)
        target = date.fromisoformat(goal['target_date']) if goal['target_date'] else None
        deadline_state = ('completed' if goal['status'] == 'completed' else 'no_deadline' if target is None
                          else 'overdue' if goal['status'] == 'active' and target < today
                          else 'today' if goal['status'] == 'active' and target == today
                          else 'upcoming' if goal['status'] == 'active' and target > today
                          else 'paused')
        goal.update({
            'milestone_count': total,
            'completed_milestone_count': completed,
            'progress_percentage': round(100 * completed / total) if total else None,
            'is_overdue': bool(goal['status'] == 'active' and target and target < today),
            'is_upcoming': bool(goal['status'] == 'active' and target and target >= today),
            'deadline_state': deadline_state,
        })
        for milestone in milestones:
            due = date.fromisoformat(milestone['target_date']) if milestone['target_date'] else None
            milestone['is_overdue'] = bool(milestone['status'] == 'pending' and due and due < today)
            milestone['is_upcoming'] = bool(milestone['status'] == 'pending' and due and due >= today)
            milestone['deadline_state'] = ('completed' if milestone['status'] == 'completed' else 'no_deadline'
                                           if due is None else 'overdue' if due < today else 'today'
                                           if due == today else 'upcoming')
        return goal

    @staticmethod
    def _notification_spec(goal, milestone, today):
        item = milestone or goal
        if item['status'] == 'completed' and item.get('completed_at'):
            kind = 'milestone_completed' if milestone else 'goal_completed'
            event_key = f"{kind}:{item['milestone_id'] if milestone else item['goal_id']}:{item['completed_at']}"
            title = 'Milestone completed' if milestone else 'Goal completed'
            message = item['title']
            due = item.get('target_date')
            return event_key, kind, title, message, due
        if milestone and item['status'] != 'pending' or not milestone and item['status'] != 'active':
            return None
        due = date.fromisoformat(item['target_date']) if item.get('target_date') else None
        if due is None:
            return None
        if due < today:
            stage, suffix, title = 'overdue', 'overdue', 'Milestone overdue' if milestone else 'Goal overdue'
        elif due == today:
            stage, suffix, title = 'due_today', 'due today', 'Milestone due today' if milestone else 'Goal due today'
        elif (due - today).days <= 7:
            stage, suffix, title = 'upcoming', 'coming up', 'Milestone deadline coming up' if milestone else 'Goal deadline coming up'
        else:
            return None
        kind = f"{'milestone' if milestone else 'goal'}_{stage}"
        object_id = item['milestone_id'] if milestone else item['goal_id']
        event_key = f"deadline:{'milestone' if milestone else 'goal'}:{object_id}:{item['target_date']}"
        noun = 'milestone' if milestone else 'goal'
        message = f"{item['title']} is {suffix} ({item['target_date']})."
        return event_key, kind, title, message, item['target_date']

    def _sync_notifications(self, connection, identity, profile_id, today):
        goals = connection.execute('SELECT * FROM goals WHERE profile_id=? AND account_id=? ORDER BY goal_id',
                                   (profile_id, identity.account_id)).fetchall()
        specs = []
        for row in goals:
            goal = dict(row)
            goal_spec = self._notification_spec(goal, None, today)
            if goal_spec:
                specs.append((goal, None, goal_spec))
            for milestone_row in connection.execute(
                    'SELECT * FROM milestones WHERE goal_id=? AND profile_id=? AND account_id=? ORDER BY milestone_id',
                    (goal['goal_id'], profile_id, identity.account_id)):
                milestone = dict(milestone_row)
                # Completed goals suppress outstanding deadline alerts, while their actual completions remain useful.
                spec = self._notification_spec(goal, milestone, today)
                if spec and (milestone['status'] == 'completed' or goal['status'] == 'active'):
                    specs.append((goal, milestone, spec))

        event_keys = {spec[2][0] for spec in specs}
        existing = connection.execute('SELECT event_key,kind FROM notifications WHERE profile_id=? AND account_id=?',
                                       (profile_id, identity.account_id)).fetchall()
        for row in existing:
            if row['event_key'] not in event_keys:
                connection.execute('DELETE FROM notifications WHERE event_key=? AND profile_id=? AND account_id=?',
                                   (row['event_key'], profile_id, identity.account_id))
        now = _stamp(self.clock())
        for goal, milestone, spec in specs:
            event_key, kind, title, message, relevant_date = spec
            existing_row = connection.execute('SELECT notification_id,kind,read_at FROM notifications '
                                               'WHERE event_key=? AND profile_id=? AND account_id=?',
                                               (event_key, profile_id, identity.account_id)).fetchone()
            if existing_row:
                read_at = existing_row['read_at'] if existing_row['kind'] == kind else None
                created_at = None if existing_row['kind'] == kind else now
                connection.execute('UPDATE notifications SET kind=?,title=?,message=?,relevant_date=?,read_at=?,'
                                   'created_at=COALESCE(?,created_at) '
                                   'WHERE notification_id=? AND profile_id=? AND account_id=?',
                                   (kind, title, message, relevant_date, read_at, created_at, existing_row['notification_id'],
                                    profile_id, identity.account_id))
            else:
                connection.execute('INSERT INTO notifications(notification_id,profile_id,account_id,goal_id,milestone_id,'
                                   'event_key,kind,title,message,relevant_date,created_at,read_at) '
                                   'VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL)',
                                   (str(uuid.uuid4()), profile_id, identity.account_id, goal['goal_id'],
                                    milestone['milestone_id'] if milestone else None, event_key, kind, title, message,
                                    relevant_date, now))

    @staticmethod
    def _notification_result(row):
        item = dict(row)
        item['is_read'] = item['read_at'] is not None
        return item

    def list_notifications(self, identity, profile_id, unread_only=False):
        self._authorize(identity, profile_id)
        today = self.clock().date()
        with self.store.transaction() as connection:
            self._ensure_profile(connection, identity, profile_id)
            self._sync_notifications(connection, identity, profile_id, today)
            where = ' AND n.read_at IS NULL' if unread_only else ''
            rows = connection.execute('SELECT n.*,g.title AS goal_title,m.title AS milestone_title '
                                      'FROM notifications n JOIN goals g ON g.goal_id=n.goal_id '
                                      'AND g.profile_id=n.profile_id AND g.account_id=n.account_id '
                                      'LEFT JOIN milestones m ON m.milestone_id=n.milestone_id '
                                      'AND m.goal_id=n.goal_id AND m.profile_id=n.profile_id AND m.account_id=n.account_id '
                                      'WHERE n.profile_id=? AND n.account_id=?' + where +
                                      ' ORDER BY n.created_at DESC,n.notification_id DESC',
                                      (profile_id, identity.account_id)).fetchall()
            count = connection.execute('SELECT count(*) FROM notifications WHERE profile_id=? AND account_id=? AND read_at IS NULL',
                                       (profile_id, identity.account_id)).fetchone()[0]
            return {'notifications': [self._notification_result(row) for row in rows],
                    'unread_count': count, 'as_of_date': today.isoformat(), 'timezone': 'UTC'}

    def unread_notification_count(self, identity, profile_id):
        return self.list_notifications(identity, profile_id, unread_only=True)['unread_count']

    def mark_notification_read(self, identity, profile_id, notification_id):
        self._authorize(identity, profile_id)
        if not _goal_id(notification_id):
            raise GoalNotFound()
        now = _stamp(self.clock())
        with self.store.transaction() as connection:
            result = connection.execute('UPDATE notifications SET read_at=COALESCE(read_at,?) '
                                        'WHERE notification_id=? AND profile_id=? AND account_id=?',
                                        (now, notification_id, profile_id, identity.account_id))
            if result.rowcount != 1:
                raise GoalNotFound()
            return connection.execute('SELECT count(*) FROM notifications WHERE profile_id=? AND account_id=? AND read_at IS NULL',
                                      (profile_id, identity.account_id)).fetchone()[0]

    def mark_all_notifications_read(self, identity, profile_id):
        self._authorize(identity, profile_id)
        now = _stamp(self.clock())
        with self.store.transaction() as connection:
            self._sync_notifications(connection, identity, profile_id, self.clock().date())
            connection.execute('UPDATE notifications SET read_at=? WHERE profile_id=? AND account_id=? AND read_at IS NULL',
                               (now, profile_id, identity.account_id))
            return 0

    def list_goals(self, identity, profile_id):
        self._authorize(identity, profile_id)
        today = self.clock().date()
        with self.store.transaction() as connection:
            self._ensure_profile(connection, identity, profile_id)
            rows = connection.execute('SELECT * FROM goals WHERE profile_id=? AND account_id=? '
                                      'ORDER BY CASE priority WHEN \'high\' THEN 0 WHEN \'medium\' THEN 1 ELSE 2 END, '
                                      'CASE WHEN target_date IS NULL THEN 1 ELSE 0 END,target_date,created_at,goal_id',
                                      (profile_id, identity.account_id)).fetchall()
            goals = [self._serialize_goal(self._goal(connection, identity, profile_id, row['goal_id']), today)
                     for row in rows]
            milestones = [item for goal in goals for item in goal['milestones'] if item['status'] == 'pending']
            return {
                'goals': goals,
                'as_of': today.isoformat(),
                'summary': {
                    'active_goals': sum(goal['status'] == 'active' for goal in goals),
                    'completed_goals': sum(goal['status'] == 'completed' for goal in goals),
                    'upcoming_milestones': sum(item['is_upcoming'] for item in milestones),
                    'overdue_milestones': sum(item['is_overdue'] for item in milestones),
                },
            }

    def create_goal(self, identity, profile_id, values):
        self._authorize(identity, profile_id)
        now, goal_id = _stamp(self.clock()), str(uuid.uuid4())
        target = values['target_date'].isoformat() if values.get('target_date') else None
        with self.store.transaction() as connection:
            self._ensure_profile(connection, identity, profile_id)
            connection.execute('INSERT INTO goals(goal_id,profile_id,account_id,title,description,category,target_date,'
                               'priority,status,related_module,created_at,updated_at,completed_at) '
                               'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL)',
                               (goal_id, profile_id, identity.account_id, values['title'], values.get('description', ''),
                                values['category'], target, values['priority'], 'active', values.get('related_module'), now, now))
            return self._serialize_goal(self._goal(connection, identity, profile_id, goal_id), self.clock().date())

    def update_goal(self, identity, profile_id, goal_id, values):
        self._authorize(identity, profile_id)
        if not _goal_id(goal_id):
            raise GoalNotFound()
        now = _stamp(self.clock())
        with self.store.transaction() as connection:
            current = self._goal(connection, identity, profile_id, goal_id)
            updates = {}
            for name, value in values.items():
                updates[name] = value.isoformat() if name == 'target_date' and value else value
            status = updates.get('status', current['status'])
            completed_at = (current['completed_at'] if current['status'] == 'completed' and status == 'completed'
                            else now if status == 'completed' else None)
            updates.update(updated_at=now, completed_at=completed_at)
            columns = ','.join(f'{name}=?' for name in updates)
            try:
                connection.execute(f'UPDATE goals SET {columns} WHERE goal_id=? AND profile_id=? AND account_id=?',
                                   (*updates.values(), goal_id, profile_id, identity.account_id))
            except Exception as error:
                if 'Complete every milestone' in str(error):
                    raise GoalConflict('Complete all milestones before marking this goal complete.') from None
                raise
            return self._serialize_goal(self._goal(connection, identity, profile_id, goal_id), self.clock().date())

    def delete_goal(self, identity, profile_id, goal_id):
        self._authorize(identity, profile_id)
        if not _goal_id(goal_id):
            raise GoalNotFound()
        with self.store.transaction() as connection:
            row = connection.execute('DELETE FROM goals WHERE goal_id=? AND profile_id=? AND account_id=?',
                                     (goal_id, profile_id, identity.account_id))
            if row.rowcount != 1:
                raise GoalNotFound()

    def create_milestone(self, identity, profile_id, goal_id, values):
        self._authorize(identity, profile_id)
        if not _goal_id(goal_id):
            raise GoalNotFound()
        now, milestone_id = _stamp(self.clock()), str(uuid.uuid4())
        target = values['target_date'].isoformat() if values.get('target_date') else None
        with self.store.transaction() as connection:
            goal = self._goal(connection, identity, profile_id, goal_id)
            if goal['status'] == 'completed':
                raise GoalConflict('Reopen the goal before adding a milestone.')
            connection.execute('INSERT INTO milestones(milestone_id,goal_id,profile_id,account_id,title,description,'
                               'target_date,status,created_at,updated_at,completed_at) VALUES(?,?,?,?,?,?,?,\'pending\',?,?,NULL)',
                               (milestone_id, goal_id, profile_id, identity.account_id, values['title'],
                                values.get('description', ''), target, now, now))
            return self._serialize_goal(self._goal(connection, identity, profile_id, goal_id), self.clock().date())

    def update_milestone(self, identity, profile_id, goal_id, milestone_id, values):
        self._authorize(identity, profile_id)
        if not _goal_id(goal_id) or not _goal_id(milestone_id):
            raise GoalNotFound()
        now = _stamp(self.clock())
        with self.store.transaction() as connection:
            goal = self._goal(connection, identity, profile_id, goal_id)
            milestone = connection.execute('SELECT * FROM milestones WHERE milestone_id=? AND goal_id=? '
                                           'AND profile_id=? AND account_id=?',
                                           (milestone_id, goal_id, profile_id, identity.account_id)).fetchone()
            if not milestone:
                raise GoalNotFound()
            updates = {name: (value.isoformat() if name == 'target_date' and value else value)
                       for name, value in values.items()}
            status = updates.get('status', milestone['status'])
            if goal['status'] == 'completed' and status != 'completed':
                raise GoalConflict('Reopen the goal before reopening a completed milestone.')
            completed_at = (milestone['completed_at'] if milestone['status'] == 'completed' and status == 'completed'
                            else now if status == 'completed' else None)
            updates.update(updated_at=now, completed_at=completed_at)
            columns = ','.join(f'{name}=?' for name in updates)
            connection.execute(f'UPDATE milestones SET {columns} WHERE milestone_id=? AND goal_id=? '
                               'AND profile_id=? AND account_id=?',
                               (*updates.values(), milestone_id, goal_id, profile_id, identity.account_id))
            return self._serialize_goal(self._goal(connection, identity, profile_id, goal_id), self.clock().date())

    def delete_milestone(self, identity, profile_id, goal_id, milestone_id):
        self._authorize(identity, profile_id)
        if not _goal_id(goal_id) or not _goal_id(milestone_id):
            raise GoalNotFound()
        with self.store.transaction() as connection:
            self._goal(connection, identity, profile_id, goal_id)
            result = connection.execute('DELETE FROM milestones WHERE milestone_id=? AND goal_id=? '
                                        'AND profile_id=? AND account_id=?',
                                        (milestone_id, goal_id, profile_id, identity.account_id))
            if result.rowcount != 1:
                raise GoalNotFound()
