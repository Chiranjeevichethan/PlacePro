import './authFixtures.js';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { fetchGoalNotifications, fetchUnreadNotificationCount, markAllGoalNotificationsRead,
  markGoalNotificationRead } from '../src/services/goalsApi.js';
import { goalDeadlineLabel, goalDraftFromAction, goalDraftFromRoadmap, goalProgressLabel,
  milestoneDeadlineLabel } from '../src/services/goalPresentation.js';

const component = await readFile(new URL('../src/components/GoalManagement.jsx', import.meta.url), 'utf8');
const api = await readFile(new URL('../src/services/goalsApi.js', import.meta.url), 'utf8');
const career = await readFile(new URL('../src/pages/CareerReadiness.jsx', import.meta.url), 'utf8');
const app = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
const css = await readFile(new URL('../src/App.css', import.meta.url), 'utf8');

test('notification API uses the backend profile-level paths and authenticated transport', async (t) => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response(JSON.stringify({ notifications: [], unread_count: 0 }), {
      headers: { 'Content-Type': 'application/json' },
    });
  });
  const profileId = 'owned-profile-123';
  await fetchGoalNotifications(profileId);
  await fetchGoalNotifications(profileId, true);
  await fetchUnreadNotificationCount(profileId);
  await markGoalNotificationRead(profileId, 'notification-123');
  await markAllGoalNotificationsRead(profileId);

  assert.deepEqual(calls.map(({ url }) => new URL(url).pathname + new URL(url).search), [
    `/api/profile/${profileId}/notifications`,
    `/api/profile/${profileId}/notifications?unread_only=true`,
    `/api/profile/${profileId}/notifications/unread-count`,
    `/api/profile/${profileId}/notifications/notification-123`,
    `/api/profile/${profileId}/notifications/read-all`,
  ]);
  assert.deepEqual(calls.map(({ init }) => init.method), ['GET', 'GET', 'GET', 'PUT', 'POST']);
  assert.ok(calls.every(({ init }) => init.credentials === 'include' && init.cache === 'no-store'));
  assert.equal(calls[3].init.headers['x-csrf-token'], 'a'.repeat(64));
  assert.equal(calls[4].init.headers['x-csrf-token'], 'a'.repeat(64));
});

test('recommendation drafts use existing action fields and do not create goals automatically', () => {
  assert.deepEqual(goalDraftFromAction({
    title: 'Practise SQL joins', description: 'Backend reason', skill: 'SQL', priority: 'High', destination: 'skillgap',
  }), {
    title: 'Practise SQL joins', description: 'Backend reason', category: 'skill', target_date: '', priority: 'high', related_module: 'skillgap',
  });
  assert.deepEqual(goalDraftFromAction({
    title: 'Review profile', priority: 'Optional', destination: 'edit-profile',
  }), {
    title: 'Review profile', description: '', category: 'profile', target_date: '', priority: 'low', related_module: 'profile',
  });
  assert.match(component, /Use as a goal draft/);
  assert.match(component, /it is not saved until you create it/);
});

test('goal progress labels use server calculations and keep zero-milestone progress unavailable', () => {
  assert.equal(goalProgressLabel({ progress_percentage: null, milestone_count: 0 }), 'No milestones yet');
  assert.equal(goalProgressLabel({ progress_percentage: 0, completed_milestone_count: 0, milestone_count: 3 }), '0% · 0 of 3 milestones complete');
  assert.equal(goalProgressLabel({ progress_percentage: 67, completed_milestone_count: 2, milestone_count: 3 }), '67% · 2 of 3 milestones complete');
  assert.equal(goalDeadlineLabel({ target_date: '2026-11-10', is_overdue: true }), 'Overdue · 2026-11-10');
  assert.equal(goalDeadlineLabel({ target_date: '2026-11-20', is_upcoming: true }), 'Upcoming · 2026-11-20');
  assert.equal(goalDeadlineLabel({ target_date: null }), 'No target date');
  assert.equal(goalDeadlineLabel({ target_date: '2026-11-14', deadline_state: 'today' }), 'Due today · 2026-11-14');
  assert.equal(goalDeadlineLabel({ target_date: '2026-11-14', status: 'completed' }), 'Completed');
  assert.equal(goalDeadlineLabel({ target_date: null, deadline_state: 'paused', status: 'paused' }), 'Paused · no deadline');
  assert.equal(milestoneDeadlineLabel({ deadline_state: 'today' }), 'Due today');
  assert.equal(milestoneDeadlineLabel({ deadline_state: 'completed' }), 'Completed');
});

test('notifications are integrated with navigation, owned API actions, and goal/milestone focus', async () => {
  const center = await readFile(new URL('../src/pages/NotificationCenter.jsx', import.meta.url), 'utf8');
  const sidebar = await readFile(new URL('../src/components/Sidebar.jsx', import.meta.url), 'utf8');
  const navbar = await readFile(new URL('../src/components/Navbar.jsx', import.meta.url), 'utf8');
  assert.match(api, /export const fetchGoalNotifications/);
  assert.match(api, /export const fetchUnreadNotificationCount/);
  assert.match(api, /export const markGoalNotificationRead/);
  assert.match(api, /export const markAllGoalNotificationsRead/);
  assert.match(center, /Unread only/);
  assert.match(center, /Mark all read/);
  assert.match(center, /No unread notifications/);
  assert.match(center, /role="status" aria-live="polite" aria-atomic="true">\{statusMessage\}/);
  assert.match(center, /setStatusMessage\('Notifications marked as read\.'\)/);
  assert.match(center, /Retry/);
  assert.match(center, /onOpenGoal\?\.\(notification\)/);
  assert.match(center, /role="alert"/);
  assert.match(sidebar, /page: "notifications"/);
  assert.match(navbar, /unreadNotificationCount/);
  assert.match(component, /id=\{`goal-\$\{goal\.goal_id\}`\}/);
  assert.match(component, /id=\{`milestone-\$\{milestone\.milestone_id\}`\}/);
  assert.match(component, /heading\?\.focus/);
  assert.match(component, /milestoneDeadlineLabel/);
  assert.match(app, /<NotificationCenter/);
  assert.match(app, /setNotificationTarget\(\{ goalId: notification\.goal_id, milestoneId: notification\.milestone_id \}\)/);
  assert.match(app, /placepro-goals-changed/);
});

test('roadmap activity can prefill an explicit student goal draft with its sequence and module', () => {
  assert.deepEqual(goalDraftFromRoadmap({
    title: 'SQL preparation sequence', skill: 'SQL', priority: 'High',
    reason: 'The backend marked the gap HIGH.',
    steps: [{ title: 'Review SQL guidance', destination: 'skillgap' }, { title: 'Practise SQL', destination: 'mocktests' }],
  }), {
    title: 'SQL preparation sequence',
    description: 'The backend marked the gap HIGH.\nPreparation sequence: Review SQL guidance → Practise SQL.',
    category: 'skill', target_date: '', priority: 'high', related_module: 'skillgap',
  });
});

test('goal API uses authenticated profile-scoped endpoints and sends no client owner identifier', () => {
  assert.match(api, /authenticatedFetch\(pathFor\(profileId, suffix\)/);
  assert.match(api, /export const createStudentGoal/);
  assert.match(api, /export const updateStudentGoal/);
  assert.match(api, /export const deleteStudentGoal/);
  assert.match(api, /export const createGoalMilestone/);
  assert.match(api, /export const updateGoalMilestone/);
  assert.match(api, /export const deleteGoalMilestone/);
  assert.doesNotMatch(api, /account_id|student_id|localStorage|sessionStorage/);
});

test('Career Readiness integrates saved goals without changing Mock Tests mounted state', () => {
  assert.match(career, /<GoalManagement profileId=\{data\.profile_id\} actions=\{view\.actions\}/);
  assert.match(career, /roadmap=\{roadmap\}/);
  assert.match(component, /Turn a Learning Roadmap sequence into a goal/);
  assert.match(component, /if \(!active\) return undefined/);
  assert.match(component, /onNavigate\(destinationFor\(goal\.related_module\)\)/);
  assert.match(app, /<div hidden=\{currentPage !== "mocktests"\}>\s*<MockTests onNavigate=\{handleNavigate\}[\s\S]*?onAssessmentStateChange=\{handleAssessmentStateChange\}/);
});

test('goal UI has explicit completion, deletion confirmation, loading/error/empty and modal semantics', () => {
  assert.match(component, /Mark goal complete/);
  assert.match(component, /Complete every milestone before completing this goal/);
  assert.match(component, /Mark complete/);
  assert.match(component, /Delete this goal\?/);
  assert.match(component, /permanently removed/);
  assert.match(component, /No goals yet/);
  assert.match(component, /Loading saved goals/);
  assert.match(component, /role="alert"/);
  assert.match(component, /Retry/);
  assert.match(component, /labelledBy=/);
  assert.match(component, /describedBy=/);
  assert.doesNotMatch(component, /localStorage|sessionStorage|type="checkbox"/);
});

test('goals and milestones retain tablet and mobile layouts', () => {
  assert.match(css, /\.goal-summary-grid\s*\{[^}]*grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media\s*\(max-width:\s*900px\)[\s\S]*?\.goal-summary-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.student-milestones li\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/);
  assert.match(css, /\.goal-form-modal\s*\{[^}]*max-height/);
});
