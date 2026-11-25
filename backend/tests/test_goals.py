from datetime import datetime, timezone
import sqlite3
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.services.password_service import PasswordService
from backend.app.services.security_config import SecurityConfig
from backend.tests.test_profile_ownership import body as profile_body
from backend.tests.test_profile_ownership import create as create_profile
from backend.tests.test_session_security import BASE, ORIGIN, csrf, login
from backend.tests.test_sessions import PASSWORD


@pytest.fixture(scope='module')
def goal_password_hash():
    return PasswordService().hash_password(PASSWORD)


@pytest.fixture
def goal_pair(isolated_storage, goal_password_hash):
    app = create_app(SecurityConfig(origins=(ORIGIN,)))
    for email in ('one@example.org', 'two@example.org'):
        app.state.accounts.store.create_account(email, goal_password_hash)
    with sqlite3.connect(isolated_storage.auth_db) as connection:
        connection.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-09T00:00:00+00:00'")
    with TestClient(app, base_url=BASE) as first, TestClient(app, base_url=BASE) as second:
        assert login(first).status_code == 200
        assert login(second, email='two@example.org').status_code == 200
        headers_a, headers_b = csrf(first), csrf(second)
        profile_a = create_profile(first, headers_a)
        body_b = profile_body()
        body_b['personal']['email'] = 'two@example.org'
        profile_b_response = second.post('/api/profile/verify', headers=headers_b, json=body_b)
        assert profile_b_response.status_code == 200, profile_b_response.text
        yield app, first, second, headers_a, headers_b, profile_a, profile_b_response.json()['profile'], isolated_storage


@pytest.fixture
def goal_clock(goal_pair):
    app = goal_pair[0]
    fixed = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    app.state.owned_goals.clock = lambda: fixed
    return fixed


def goal_url(profile, suffix=''):
    return f"/api/profile/{profile['profile_id']}/goals{suffix}"


def goal_body(**overrides):
    return {
        'title': 'Strengthen SQL queries',
        'description': 'Practise the query skills named in my readiness plan.',
        'category': 'skill',
        'target_date': '2026-11-21',
        'priority': 'high',
        'related_module': 'skillgap',
        **overrides,
    }


def create_goal(client, headers, profile, **overrides):
    response = client.post(goal_url(profile), headers=headers, json=goal_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_goal_crud_is_persistent_validated_and_profile_owned(goal_pair, goal_clock):
    app, first, second, headers_a, headers_b, profile_a, profile_b, storage = goal_pair
    goal = create_goal(first, headers_a, profile_a)
    assert goal['status'] == 'active' and goal['progress_percentage'] is None
    assert goal['target_date'] == '2026-11-21' and goal['is_upcoming'] is True

    listing = first.get(goal_url(profile_a))
    assert listing.status_code == 200
    assert listing.json()['summary'] == {
        'active_goals': 1, 'completed_goals': 0, 'upcoming_milestones': 0, 'overdue_milestones': 0,
    }
    update = first.put(goal_url(profile_a, f"/{goal['goal_id']}"), headers=headers_a,
                       json={'title': 'Build reliable SQL fluency', 'target_date': None})
    assert update.status_code == 200 and update.json()['target_date'] is None

    assert second.get(goal_url(profile_a)).status_code == 404
    foreign_goal = second.put(goal_url(profile_b, f"/{goal['goal_id']}"), headers=headers_b,
                              json={'title': 'Attempt foreign update'})
    assert foreign_goal.status_code == 404
    assert first.put(goal_url(profile_a, '/not-a-uuid'), headers=headers_a,
                     json={'title': 'Invalid goal identifier'}).status_code == 404

    restarted = create_app(SecurityConfig(origins=(ORIGIN,)))
    with TestClient(restarted, base_url=BASE) as restored:
        restored.cookies.set(app.state.security_config.cookie_name,
                            first.cookies.get(app.state.security_config.cookie_name))
        loaded = restored.get(goal_url(profile_a))
        assert loaded.status_code == 200 and loaded.json()['goals'][0]['title'] == 'Build reliable SQL fluency'

    deleted = first.delete(goal_url(profile_a, f"/{goal['goal_id']}"), headers=headers_a)
    assert deleted.status_code == 204
    assert first.get(goal_url(profile_a)).json()['goals'] == []
    assert storage.goals_db.is_file()


def test_milestones_drive_progress_and_goal_completion_requires_explicit_saved_milestones(goal_pair, goal_clock):
    _, first, _, headers, _, profile, _, _ = goal_pair
    goal = create_goal(first, headers, profile)
    due = first.post(goal_url(profile, f"/{goal['goal_id']}/milestones"), headers=headers, json={
        'title': 'Review SQL joins', 'description': 'Use the current skill-gap guidance.', 'target_date': '2026-11-13',
    })
    assert due.status_code == 201
    milestone = due.json()['milestones'][0]
    assert milestone['is_overdue'] is True and due.json()['progress_percentage'] == 0
    summary = first.get(goal_url(profile)).json()['summary']
    assert summary['overdue_milestones'] == 1

    blocked = first.put(goal_url(profile, f"/{goal['goal_id']}"), headers=headers, json={'status': 'completed'})
    assert blocked.status_code == 409 and 'all milestones' in blocked.json()['detail']

    updated = first.put(goal_url(profile, f"/{goal['goal_id']}/milestones/{milestone['milestone_id']}"),
                        headers=headers, json={'status': 'completed'})
    assert updated.status_code == 200
    completed_milestone = updated.json()['milestones'][0]
    assert completed_milestone['completed_at'] and completed_milestone['is_overdue'] is False
    assert updated.json()['progress_percentage'] == 100
    completion_stamp = completed_milestone['completed_at']
    milestone_edit = first.put(goal_url(profile, f"/{goal['goal_id']}/milestones/{milestone['milestone_id']}"),
                               headers=headers, json={'title': 'Review SQL joins and filters'})
    assert milestone_edit.status_code == 200
    assert milestone_edit.json()['milestones'][0]['completed_at'] == completion_stamp

    completed_goal = first.put(goal_url(profile, f"/{goal['goal_id']}"), headers=headers,
                               json={'status': 'completed'})
    assert completed_goal.status_code == 200 and completed_goal.json()['completed_at']
    goal_stamp = completed_goal.json()['completed_at']
    goal_edit = first.put(goal_url(profile, f"/{goal['goal_id']}"), headers=headers,
                          json={'description': 'Updated note; original completion date is retained.'})
    assert goal_edit.status_code == 200 and goal_edit.json()['completed_at'] == goal_stamp
    assert first.get(goal_url(profile)).json()['summary']['completed_goals'] == 1
    assert first.post(goal_url(profile, f"/{goal['goal_id']}/milestones"), headers=headers,
                      json={'title': 'Should not be added to a completed goal'}).status_code == 409

    reopened = first.put(goal_url(profile, f"/{goal['goal_id']}"), headers=headers, json={'status': 'active'})
    assert reopened.status_code == 200 and reopened.json()['completed_at'] is None
    pending = first.put(goal_url(profile, f"/{goal['goal_id']}/milestones/{milestone['milestone_id']}"),
                        headers=headers, json={'status': 'pending'})
    assert pending.status_code == 200 and pending.json()['progress_percentage'] == 0


@pytest.mark.parametrize('payload', [
    {},
    {'title': '   '},
    {'title': 'Invalid status', 'status': 'completed'},
    {'title': 'Bad date', 'target_date': '2026-02-30'},
    {'title': 'Client owner', 'account_id': 'someone-else'},
    {'title': 'Unknown module', 'related_module': 'external-course'},
])
def test_goal_input_rejects_missing_invalid_and_client_owned_fields(goal_pair, payload):
    _, first, _, headers, _, profile, _, _ = goal_pair
    response = first.post(goal_url(profile), headers=headers, json=payload)
    assert response.status_code == 422


def test_milestone_input_rejects_invalid_payload_and_status(goal_pair):
    _, first, _, headers, _, profile, _, _ = goal_pair
    goal = create_goal(first, headers, profile)
    route = goal_url(profile, f"/{goal['goal_id']}/milestones")
    assert first.post(route, headers=headers, json={'title': '   '}).status_code == 422
    assert first.post(route, headers=headers, json={'title': 'Bad date', 'target_date': 'not-a-date'}).status_code == 422
    assert first.post(route, headers=headers, json={'title': 'Fake completion', 'status': 'completed'}).status_code == 422


def test_goal_routes_require_session_csrf_and_reject_expired_session(goal_pair):
    app, first, _, headers, _, profile, _, storage = goal_pair
    url = goal_url(profile)
    anonymous = TestClient(app, base_url=BASE)
    assert anonymous.get(url).status_code == 401
    assert not storage.goals_db.exists()
    assert first.post(url, json=goal_body(), headers={'Origin': ORIGIN}).status_code == 403

    original_clock = app.state.sessions.clock
    app.state.sessions.clock = lambda: original_clock() + app.state.security_config.absolute_seconds + 1
    try:
        assert first.get(url).status_code == 401
    finally:
        app.state.sessions.clock = original_clock


def test_database_constraints_and_schema_refuse_unrelated_or_modified_databases(goal_pair, goal_clock):
    _, first, _, headers, _, profile, _, storage = goal_pair
    create_goal(first, headers, profile)
    with sqlite3.connect(storage.goals_db) as connection:
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE goals SET status='completed',completed_at=NULL")

    unrelated = storage.root / 'unrelated.sqlite3'
    with sqlite3.connect(unrelated) as connection:
        connection.execute('CREATE TABLE private_data (secret TEXT)')
    from backend.app.services.goals_store import GoalStorageUnavailable, GoalsStore
    with pytest.raises(GoalStorageUnavailable):
        with GoalsStore(unrelated).transaction():
            pass


def test_notifications_are_idempotent_classified_and_read_state_is_persisted(goal_pair, goal_clock):
    app, first, _, headers, _, profile, _, storage = goal_pair
    goal = create_goal(first, headers, profile, target_date='2026-11-21')
    created = first.post(goal_url(profile, f"/{goal['goal_id']}/milestones"), headers=headers, json={
        'title': 'Submit practice project', 'target_date': '2026-11-13',
    })
    assert created.status_code == 201
    milestone = created.json()['milestones'][0]
    url = f"/api/profile/{profile['profile_id']}/notifications"

    result = first.get(url)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload['timezone'] == 'UTC' and payload['as_of_date'] == '2026-11-14'
    assert {item['kind'] for item in payload['notifications']} == {'goal_upcoming', 'milestone_overdue'}
    assert payload['unread_count'] == 2
    overdue = next(item for item in payload['notifications'] if item['kind'] == 'milestone_overdue')
    assert overdue['goal_title'] == goal['title'] and overdue['milestone_title'] == 'Submit practice project'

    repeated = first.get(url).json()
    assert {item['notification_id'] for item in repeated['notifications']} == {
        item['notification_id'] for item in payload['notifications']
    }
    assert repeated['unread_count'] == 2
    assert first.get(url + '?unread_only=true').json()['unread_count'] == 2

    read = first.put(url + f"/{overdue['notification_id']}", headers=headers, json={'read': True})
    assert read.status_code == 200 and read.json()['unread_count'] == 1
    assert first.get(url + '?unread_only=true').json()['unread_count'] == 1
    assert first.put(url + f"/{overdue['notification_id']}", headers=headers, json={'read': False}).status_code == 422
    assert first.get(url + '/unread-count').json() == {'unread_count': 1}

    # Moving an item out of the notification window prunes its stale deadline alert.
    updated = first.put(goal_url(profile, f"/{goal['goal_id']}/milestones/{milestone['milestone_id']}"),
                        headers=headers, json={'target_date': '2026-12-01'})
    assert updated.status_code == 200
    after_edit = first.get(url).json()
    assert all(item['milestone_id'] != milestone['milestone_id'] for item in after_edit['notifications'])
    assert after_edit['unread_count'] == 1

    mark_all = first.post(url + '/read-all', headers=headers, json={})
    assert mark_all.status_code == 200 and mark_all.json()['unread_count'] == 0
    assert first.get(url + '?unread_only=true').json()['notifications'] == []
    with sqlite3.connect(storage.goals_db) as connection:
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []


def test_due_today_completion_and_deleted_source_records_have_no_stale_deadlines(goal_pair, goal_clock):
    _, first, _, headers, _, profile, _, _ = goal_pair
    goal = create_goal(first, headers, profile, target_date='2026-11-14')
    created = first.post(goal_url(profile, f"/{goal['goal_id']}/milestones"), headers=headers, json={
        'title': 'Today milestone', 'target_date': '2026-11-14',
    })
    milestone = created.json()['milestones'][0]
    assert milestone['deadline_state'] == 'today'
    notifications_url = f"/api/profile/{profile['profile_id']}/notifications"
    assert {item['kind'] for item in first.get(notifications_url).json()['notifications']} == {
        'goal_due_today', 'milestone_due_today',
    }

    completed = first.put(goal_url(profile, f"/{goal['goal_id']}/milestones/{milestone['milestone_id']}"),
                          headers=headers, json={'status': 'completed'})
    assert completed.status_code == 200
    after = first.get(notifications_url).json()['notifications']
    assert 'milestone_due_today' not in {item['kind'] for item in after}
    assert 'milestone_completed' in {item['kind'] for item in after}
    assert 'goal_due_today' in {item['kind'] for item in after}

    completed_goal = first.put(goal_url(profile, f"/{goal['goal_id']}"), headers=headers, json={'status': 'completed'})
    assert completed_goal.status_code == 200
    completed_notifications = first.get(notifications_url).json()['notifications']
    assert 'goal_due_today' not in {item['kind'] for item in completed_notifications}
    assert 'goal_completed' in {item['kind'] for item in completed_notifications}

    removed = first.delete(goal_url(profile, f"/{goal['goal_id']}/milestones/{milestone['milestone_id']}"), headers=headers)
    assert removed.status_code == 204
    assert all(item['milestone_id'] != milestone['milestone_id'] for item in first.get(notifications_url).json()['notifications'])


def test_due_today_notification_transitions_once_to_overdue_at_utc_date_boundary(goal_pair, goal_clock):
    app, first, _, headers, _, profile, _, _ = goal_pair
    goal = create_goal(first, headers, profile, target_date='2026-11-14')
    notifications_url = f"/api/profile/{profile['profile_id']}/notifications"
    due = first.get(notifications_url).json()['notifications'][0]
    assert due['kind'] == 'goal_due_today' and due['relevant_date'] == '2026-11-14'
    assert first.put(notifications_url + f"/{due['notification_id']}", headers=headers,
                     json={'read': True}).json()['unread_count'] == 0

    app.state.owned_goals.clock = lambda: datetime(2026, 11, 15, 0, 1, tzinfo=timezone.utc)
    overdue = first.get(notifications_url).json()
    assert overdue['as_of_date'] == '2026-11-15' and overdue['timezone'] == 'UTC'
    assert len(overdue['notifications']) == 1
    assert overdue['notifications'][0]['notification_id'] == due['notification_id']
    assert overdue['notifications'][0]['kind'] == 'goal_overdue'
    assert overdue['notifications'][0]['is_read'] is False
    assert overdue['unread_count'] == 1


def test_notification_routes_enforce_session_profile_ownership_and_csrf(goal_pair):
    app, first, second, headers_a, _, profile_a, profile_b, storage = goal_pair
    url_a = f"/api/profile/{profile_a['profile_id']}/notifications"
    url_b = f"/api/profile/{profile_b['profile_id']}/notifications"
    anonymous = TestClient(app, base_url=BASE)
    assert anonymous.get(url_a).status_code == 401
    assert first.post(url_a + '/read-all', json={}, headers={'Origin': ORIGIN}).status_code == 403
    assert not storage.goals_db.exists()
    assert second.get(url_a).status_code == 404
    assert second.get(url_b).status_code == 200


def test_legacy_goals_database_migrates_additively_without_losing_records(isolated_storage):
    from backend.app.services.goals_store import APPLICATION_ID, SCHEMA, GoalsStore

    database = isolated_storage.root / 'legacy-goals.sqlite3'
    legacy_schema = (SCHEMA.split('CREATE UNIQUE INDEX milestones_owner_link', 1)[0]
                     + 'CREATE TRIGGER goal_completed_requires_milestones'
                     + SCHEMA.split('CREATE TRIGGER goal_completed_requires_milestones', 1)[1])
    profile_id, account_id, goal_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    with sqlite3.connect(database) as connection:
        connection.executescript(legacy_schema)
        connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
        connection.execute('PRAGMA user_version=1')
        connection.execute('INSERT INTO goal_profiles VALUES(?,?,?)', (profile_id, account_id, '2026-11-14T00:00:00+00:00'))
        connection.execute('INSERT INTO goals(goal_id,profile_id,account_id,title,description,category,target_date,'
                            'priority,status,related_module,created_at,updated_at,completed_at) '
                            'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL)',
                            (goal_id, profile_id, account_id, 'Existing saved goal', '', 'preparation', '2026-11-21',
                             'medium', 'active', None, '2026-11-14T00:00:00+00:00', '2026-11-14T00:00:00+00:00'))

    with GoalsStore(database).transaction() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2
        assert connection.execute('SELECT title FROM goals WHERE goal_id=?', (goal_id,)).fetchone()[0] == 'Existing saved goal'
        assert connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='notifications'").fetchone()[0] == 1
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
