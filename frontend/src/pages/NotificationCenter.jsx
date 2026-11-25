import { useCallback, useEffect, useState } from 'react';
import { useStudentProfileContext } from '../hooks/useStudentProfileContext';
import {
  fetchGoalNotifications,
  markAllGoalNotificationsRead,
  markGoalNotificationRead,
} from '../services/goalsApi.js';

const TYPE_LABELS = {
  milestone_upcoming: 'Upcoming milestone',
  milestone_due_today: 'Milestone due today',
  milestone_overdue: 'Overdue milestone',
  goal_upcoming: 'Upcoming goal deadline',
  goal_due_today: 'Goal due today',
  goal_overdue: 'Overdue goal',
  milestone_completed: 'Milestone completed',
  goal_completed: 'Goal completed',
};

function formatDate(value) {
  if (!value) return 'Date not available';
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? 'Date not available' : new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium', timeZone: 'UTC',
  }).format(date);
}

export default function NotificationCenter({ onUnreadCountChange, onOpenGoal }) {
  const { profileId } = useStudentProfileContext();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');

  const load = useCallback(async () => {
    if (!profileId) return;
    setError(null);
    try {
      const result = await fetchGoalNotifications(profileId, unreadOnly);
      setNotifications(result.notifications || []);
      onUnreadCountChange?.(result.unread_count ?? null);
    } catch (requestError) {
      setError(requestError.message || 'Notifications are unavailable.');
    } finally {
      setLoading(false);
    }
  }, [onUnreadCountChange, profileId, unreadOnly]);

  useEffect(() => {
    let active = true;
    fetchGoalNotifications(profileId, unreadOnly).then((result) => {
      if (!active) return;
      setNotifications(result.notifications || []);
      onUnreadCountChange?.(result.unread_count ?? null);
    }).catch((requestError) => {
      if (active) setError(requestError.message || 'Notifications are unavailable.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [onUnreadCountChange, profileId, unreadOnly]);

  const markAllRead = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    setStatusMessage('');
    try {
      const result = await markAllGoalNotificationsRead(profileId);
      onUnreadCountChange?.(result.unread_count ?? 0);
      setStatusMessage('Notifications marked as read.');
      await load();
    } catch (requestError) {
      setError(requestError.message || 'Could not mark notifications as read.');
    } finally { setBusy(false); }
  };

  const openNotification = async (notification) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      let unreadCount = null;
      if (!notification.is_read) {
        const result = await markGoalNotificationRead(profileId, notification.notification_id);
        unreadCount = result.unread_count;
      }
      if (unreadCount !== null) onUnreadCountChange?.(unreadCount);
      onOpenGoal?.(notification);
    } catch (requestError) {
      setError(requestError.message || 'Could not open this notification. Retry.');
      await load();
    } finally { setBusy(false); }
  };

  return (
    <div className="notification-page">
      <header className="page-header">
        <h1>Notifications</h1>
        <p>Goal and milestone updates from your saved records. Deadline dates use PLACE PRO’s UTC calendar date.</p>
      </header>
      <section className="notification-panel" aria-labelledby="notification-list-title">
        <p className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">{statusMessage}</p>
        <div className="notification-toolbar">
          <div>
            <h2 id="notification-list-title">Your updates</h2>
            <p>Upcoming deadlines cover the next seven calendar days. An overdue item appears once and updates as its date state changes.</p>
          </div>
          <div className="notification-actions">
            <label className="notification-filter">
              <input type="checkbox" checked={unreadOnly} onChange={(event) => {
                setLoading(true); setError(null); setUnreadOnly(event.target.checked);
              }} />
              Unread only
            </label>
            <button type="button" className="dash-btn secondary" disabled={busy} onClick={markAllRead}>Mark all read</button>
          </div>
        </div>
        {error && <div className="notification-error" role="alert"><p>{error}</p>
          <button type="button" className="dash-btn secondary" onClick={() => { setLoading(true); void load(); }}>Retry</button></div>}
        {loading ? <p className="notification-state" role="status">Loading notifications…</p>
          : notifications.length === 0 ? <div className="notification-empty" role="status">
            <h3>{unreadOnly ? 'No unread notifications' : 'No notifications yet'}</h3>
            <p>{unreadOnly ? 'You are up to date with your goal and milestone notifications.'
              : 'Saved deadlines and completion records will appear here when they meet the notification rules.'}</p>
          </div> : <ul className="notification-list">
            {notifications.map((item) => (
              <li key={item.notification_id} className={`notification-item ${item.is_read ? 'is-read' : 'is-unread'}`}>
                <div className="notification-copy">
                  <div className="notification-item-heading">
                    <span className="notification-type">{TYPE_LABELS[item.kind] || 'Goal update'}</span>
                    <span className="notification-read-state">{item.is_read ? 'Read' : 'Unread'}</span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.message}</p>
                  <p className="notification-related"><strong>{item.milestone_title ? 'Milestone' : 'Goal'}:</strong> {item.milestone_title || item.goal_title}
                    {item.milestone_title && <span> · Goal: {item.goal_title}</span>}
                  </p>
                  {item.relevant_date && <time dateTime={item.relevant_date}>Date: {formatDate(item.relevant_date)}</time>}
                </div>
                <button type="button" className="dash-btn secondary" disabled={busy}
                  onClick={() => openNotification(item)}>
                  {item.is_read ? 'Open goal' : 'Mark read and open'}
                </button>
              </li>
            ))}
          </ul>}
      </section>
    </div>
  );
}
