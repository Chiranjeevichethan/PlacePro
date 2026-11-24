import { API_BASE_URL, authenticatedFetch } from './apiTransport.js';

function goalsPath(profileId, suffix = '') {
  return `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/goals${suffix}`;
}

function notificationsPath(profileId, suffix = '') {
  return `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}${suffix}`;
}

async function request(profileId, suffix, method = 'GET', payload, pathFor = goalsPath) {
  let response;
  try {
    response = await authenticatedFetch(pathFor(profileId, suffix), {
      method,
      ...(payload === undefined ? {} : {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(cause?.status ? cause.message : 'Cannot reach the goals service. Check your connection and retry.', { cause });
  }

  if (response.status === 204) return null;
  let data;
  try {
    data = await response.json();
  } catch (cause) {
    throw new Error('The goals service returned an unexpected response. Please retry.', { cause });
  }
  if (!response.ok) {
    const safeDetail = typeof data?.detail === 'string' ? data.detail : null;
    const fallback = response.status === 404 ? 'This goal or profile is no longer available.'
      : response.status === 409 ? 'The goal could not be changed in its current state.'
        : response.status === 422 ? 'Review the goal details and try again.'
          : response.status === 401 ? 'Your session has expired. Sign in again.'
            : response.status === 403 ? 'The security check failed. Refresh the page and retry.'
              : 'Unable to process this goal request. Please retry.';
    throw Object.assign(new Error(safeDetail || fallback), { status: response.status });
  }
  return data;
}

export const fetchStudentGoals = (profileId) => request(profileId, '');
export const createStudentGoal = (profileId, payload) => request(profileId, '', 'POST', payload);
export const updateStudentGoal = (profileId, goalId, payload) =>
  request(profileId, `/${encodeURIComponent(goalId)}`, 'PUT', payload);
export const deleteStudentGoal = (profileId, goalId) =>
  request(profileId, `/${encodeURIComponent(goalId)}`, 'DELETE');
export const createGoalMilestone = (profileId, goalId, payload) =>
  request(profileId, `/${encodeURIComponent(goalId)}/milestones`, 'POST', payload);
export const updateGoalMilestone = (profileId, goalId, milestoneId, payload) =>
  request(profileId, `/${encodeURIComponent(goalId)}/milestones/${encodeURIComponent(milestoneId)}`, 'PUT', payload);
export const deleteGoalMilestone = (profileId, goalId, milestoneId) =>
  request(profileId, `/${encodeURIComponent(goalId)}/milestones/${encodeURIComponent(milestoneId)}`, 'DELETE');

export const fetchGoalNotifications = (profileId, unreadOnly = false) =>
  request(profileId, `/notifications${unreadOnly ? '?unread_only=true' : ''}`, 'GET', undefined, notificationsPath);
export const fetchUnreadNotificationCount = (profileId) =>
  request(profileId, '/notifications/unread-count', 'GET', undefined, notificationsPath);
export const markGoalNotificationRead = (profileId, notificationId) =>
  request(profileId, `/notifications/${encodeURIComponent(notificationId)}`, 'PUT', { read: true }, notificationsPath);
export const markAllGoalNotificationsRead = (profileId) =>
  request(profileId, '/notifications/read-all', 'POST', {}, notificationsPath);
