import test from "node:test";
import assert from "node:assert/strict";
import {
  AUTO_SUBMIT_LEAD_MS, assessmentStorageKey, completedDuration,
  createAssessmentController, createDeadlineClock, remainingMilliseconds,
} from "../src/services/assessmentSession.js";

const origin = Date.parse("2026-11-06T10:00:00Z");
const stamp = (elapsed) => new Date(origin + elapsed).toISOString();
const profileId = "isolated-student";
const storageKey = assessmentStorageKey(profileId, "http://test.invalid");
const session = (id = "attempt-1", extra = {}) => ({
  assessment_id: id, profile_id: profileId, skill: "Python", attempt: 1,
  status: "IN_PROGRESS", total_questions: 5,
  created_at: stamp(0), expires_at: stamp(300000), server_now: stamp(0),
  submitted_at: null, result: null,
  questions: Array.from({ length: 5 }, (_, index) => ({
    question_id: "q" + index, question: "Test fixture question " + index,
    options: ["A", "B", "C", "D"], skill: "Python", topic: "Fixture", difficulty: "Easy",
  })), ...extra,
});
const report = (current, extra = {}) => ({
  assessment_id: current.assessment_id, skill: current.skill, attempt: current.attempt,
  skill_score: 40, correct: 2, total: 5, level: "Developing",
  difficulty_breakdown: { Easy: 40 }, topic_breakdown: { Fixture: 40 }, message: "Fixture result",
  ...extra,
});
const error = (message, status = null, extra = {}) => Object.assign(new Error(message), { status, ...extra });
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

function memoryStorage(initial = null) {
  const data = new Map(initial ? [[storageKey, JSON.stringify(initial)]] : []);
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), data };
}

function rig({ storage = memoryStorage(), existing = session(), overrides = {}, history = [] } = {}) {
  let elapsed = 0;
  let sequence = 0;
  const sessions = new Map([[existing.assessment_id, existing]]);
  const calls = { start: [], submit: [], get: [], completed: [], history: 0 };
  let scheduled;
  let unscheduled = 0;
  const api = {
    async start(id, skill, count) {
      calls.start.push({ id, skill, count });
      const next = session("new-" + ++sequence, { skill, attempt: sequence + 1,
        created_at: stamp(elapsed), expires_at: stamp(elapsed + count * 60000), server_now: stamp(elapsed) });
      sessions.set(next.assessment_id, next);
      return next;
    },
    async submit(id, questions, answers, owner) {
      calls.submit.push({ id, questions, answers, owner });
      const current = sessions.get(id);
      const result = report(current);
      sessions.set(id, { ...current, status: "COMPLETED", submitted_at: stamp(elapsed), result });
      return result;
    },
    async get(id) {
      calls.get.push(id);
      const current = sessions.get(id);
      if (!current) throw error("Assessment was not found", 404);
      return { ...current, server_now: stamp(elapsed),
        status: current.status === "IN_PROGRESS" && origin + elapsed >= Date.parse(current.expires_at)
          ? "EXPIRED" : current.status };
    },
    async history() { calls.history++; return { profile_id: profileId, assessments: history }; },
    ...overrides,
  };
  const controller = createAssessmentController({
    profileId, api, storage, storageKey, now: () => elapsed,
    onCompleted: (id) => calls.completed.push(id),
    schedule: (callback) => { scheduled = callback; return 1; },
    unschedule: () => { unscheduled++; },
  });
  return { controller, api, calls, sessions, storage, snapshot: controller.getSnapshot,
    setTime: (value) => { elapsed = value; }, getScheduled: () => scheduled,
    unscheduled: () => unscheduled };
}

async function started(options) {
  const current = rig(options);
  await current.controller.restore();
  current.controller.configure("Python", 5);
  await current.controller.startNew();
  return current;
}

test("start loads a confirmed session and the server deadline", async () => {
  const r = await started();
  assert.equal(r.snapshot().phase, "running");
  assert.equal(r.snapshot().secondsLeft, 300);
  assert.equal(r.snapshot().session.assessment_id, "new-1");
  assert.deepEqual(r.calls.start, [{ id: profileId, skill: "Python", count: 5 }]);
  assert.equal(r.snapshot().result, null);
});

test("initial start failure remains a visible setup error", async () => {
  const r = await started({ overrides: { start: async () => { throw error("Server offline", 503); } } });
  assert.equal(r.snapshot().phase, "setup");
  assert.match(r.snapshot().error, /Server offline/);
  assert.equal(r.snapshot().starting, false);
});

test("deadline uses server time and deducts delivery delay despite browser clock skew", (t) => {
  t.mock.method(Date, "now", () => origin - 10 * 86400000);
  const clock = createDeadlineClock(session(), 1200, 250);
  assert.equal(remainingMilliseconds(clock, 1200), 299750);
  assert.equal(remainingMilliseconds(clock, 121200), 179750);
  assert.equal(remainingMilliseconds(clock, 999999), 0);
});

for (const field of ["created_at", "expires_at", "server_now"]) {
  test("missing authoritative " + field + " fails closed", () => {
    assert.throws(() => createDeadlineClock(session("one", { [field]: null }), 0), /timing is unavailable/);
  });
}

test("a delayed timer tick uses elapsed time rather than decrementing once", async () => {
  const r = await started();
  r.setTime(120000);
  await r.controller.tick();
  assert.equal(r.snapshot().secondsLeft, 180);
});

test("auto-submit sends available answers once in the final delivery second", async () => {
  const r = await started();
  r.controller.selectAnswer("q0", 2);
  r.setTime(300000 - AUTO_SUBMIT_LEAD_MS);
  await r.controller.tick();
  await r.controller.tick();
  assert.equal(r.calls.submit.length, 1);
  assert.deepEqual(r.calls.submit[0].answers, { q0: 2 });
  assert.equal(r.snapshot().phase, "finished");
  assert.equal(r.snapshot().autoSubmitted, true);
});

test("manual submission and the expiry tick share a duplicate guard", async () => {
  const delivery = deferred();
  let requests = 0;
  const r = await started({ overrides: { submit: () => { requests++; return delivery.promise; } } });
  r.controller.selectAnswer("q0", 1);
  const submitting = r.controller.submit();
  r.setTime(299000);
  await r.controller.tick();
  await r.controller.submit();
  assert.equal(requests, 1);
  assert.equal(r.snapshot().submitting, true);
  assert.equal(r.snapshot().result, null);
  r.controller.selectAnswer("q0", 2);
  assert.deepEqual(r.snapshot().answers, { q0: 1 });
  delivery.resolve(report(r.snapshot().session));
  await submitting;
  assert.equal(r.snapshot().phase, "finished");
  assert.equal(r.snapshot().autoSubmitted, false);
});

test("a missed deadline checks expiry and never posts late answers", async () => {
  const r = await started();
  r.controller.selectAnswer("q0", 1);
  r.setTime(300000);
  await r.controller.tick();
  await r.controller.submit();
  assert.equal(r.snapshot().phase, "expired");
  assert.equal(r.snapshot().result, null);
  assert.equal(r.calls.submit.length, 0);
  assert.deepEqual(r.calls.completed, []);
});

test("HTTP 410 is terminal and cannot be retried as a scored submission", async () => {
  const r = await started({ overrides: { submit: async () => { throw error("Expired on server", 410); } } });
  r.controller.selectAnswer("q0", 1);
  await r.controller.submit();
  assert.equal(r.snapshot().phase, "expired");
  assert.match(r.snapshot().error, /Expired on server/);
  assert.equal(r.snapshot().result, null);
  assert.equal(r.snapshot().locked, true);
  assert.deepEqual(r.calls.completed, []);
});

test("automatic submission of no selected answers preserves the backend rejection without inventing a score", async () => {
  let submittedAnswers;
  const r = await started({ overrides: { submit: async (_id, _questions, answers) => {
    submittedAnswers = answers;
    throw error("No answers were provided.", 400);
  } } });
  r.setTime(299000);
  await r.controller.tick();
  assert.deepEqual(submittedAnswers, {});
  assert.equal(r.snapshot().result, null);
  assert.match(r.snapshot().error, /No answers/);
  r.setTime(300000);
  await r.controller.tick();
  assert.equal(r.snapshot().phase, "expired");
  assert.deepEqual(r.calls.completed, []);
});

test("HTTP 409 reloads the official completed result without a second POST", async () => {
  const r = await started();
  const current = r.snapshot().session;
  const official = report(current);
  r.api.submit = async (...args) => {
    r.calls.submit.push(args);
    r.sessions.set(current.assessment_id, { ...current, status: "COMPLETED", result: official, submitted_at: stamp(2000) });
    throw error("Already completed", 409);
  };
  await r.controller.submit();
  assert.equal(r.snapshot().phase, "finished");
  assert.deepEqual(r.snapshot().result, official);
  assert.equal(r.calls.submit.length, 1);
  assert.deepEqual(r.calls.completed, [profileId]);
});

test("a lost POST response is reconciled after the backend has completed", async () => {
  const r = await started();
  const submit = r.api.submit;
  r.api.submit = async (...args) => { await submit(...args); throw error("Connection lost"); };
  await r.controller.submit();
  assert.equal(r.snapshot().phase, "finished");
  assert.equal(r.calls.submit.length, 1);
  assert.equal(r.snapshot().result.skill_score, 40);
});

test("network failure before acceptance keeps answers and permits a timely retry", async () => {
  const r = await started();
  const submit = r.api.submit;
  r.api.submit = async () => { throw error("Network offline"); };
  r.controller.selectAnswer("q0", 3);
  await r.controller.submit();
  assert.equal(r.snapshot().phase, "running");
  assert.equal(r.snapshot().result, null);
  assert.match(r.snapshot().error, /Network offline/);
  assert.deepEqual(r.snapshot().answers, { q0: 3 });
  r.api.submit = submit;
  await r.controller.retrySubmission();
  assert.equal(r.snapshot().phase, "finished");
  assert.deepEqual(r.calls.submit[0].answers, { q0: 3 });
});

test("unknown delivery stays locked until status can be checked", async () => {
  const r = await started();
  const get = r.api.get;
  r.api.submit = async () => { throw error("Connection lost"); };
  r.api.get = async () => { throw error("Still offline"); };
  r.controller.selectAnswer("q0", 1);
  await r.controller.submit();
  assert.equal(r.snapshot().locked, true);
  assert.equal(r.snapshot().result, null);
  r.controller.selectAnswer("q0", 2);
  assert.deepEqual(r.snapshot().answers, { q0: 1 });
  await r.controller.retrySubmission();
  assert.equal(r.calls.submit.length, 0);
  r.api.get = get;
  await r.controller.checkStatus();
  assert.equal(r.snapshot().locked, false);
});

test("refresh restores draft answers and the elapsed server deadline", async () => {
  const storage = memoryStorage({ profileId, assessmentId: "attempt-1", answers: { q0: 2, unknown: 0, q1: 99 } });
  const r = rig({ storage });
  r.setTime(60000);
  await r.controller.restore();
  assert.equal(r.snapshot().phase, "running");
  assert.equal(r.snapshot().secondsLeft, 240);
  assert.deepEqual(r.snapshot().answers, { q0: 2 });
  assert.equal(r.calls.start.length, 0);
});

test("refresh of an expired draft never auto-submits", async () => {
  const storage = memoryStorage({ profileId, assessmentId: "attempt-1", answers: { q0: 2 } });
  const r = rig({ storage });
  r.setTime(300000);
  await r.controller.restore();
  await r.controller.tick();
  assert.equal(r.snapshot().phase, "expired");
  assert.equal(r.calls.submit.length, 0);
});

test("result refresh uses the backend report and ignores a forged cached score", async () => {
  const current = session();
  const official = report(current);
  const storage = memoryStorage({ profileId, assessmentId: current.assessment_id,
    answers: {}, result: { ...official, skill_score: 100 } });
  const r = rig({ storage, existing: { ...current, status: "COMPLETED", result: official, submitted_at: stamp(40000) } });
  await r.controller.restore();
  assert.equal(r.snapshot().result.skill_score, 40);
  assert.equal(r.snapshot().timeTakenSeconds, 40);
  assert.equal(JSON.parse(storage.getItem(storageKey)).result, undefined);
});

test("backend history restores the latest completed result when the tab has no reference", async () => {
  const current = session("history-result", { skill: "SQL", attempt: 2 });
  const r = rig({ existing: { ...current, status: "COMPLETED", result: report(current) },
    history: [{ assessment_id: "old" }, { assessment_id: current.assessment_id }] });
  await r.controller.restore();
  assert.equal(r.snapshot().phase, "finished");
  assert.equal(r.snapshot().skill, "SQL");
  assert.deepEqual(r.calls.get, ["history-result"]);
});

test("a malformed active session shows a recovery error instead of an endless loading screen", async () => {
  const storage = memoryStorage({ profileId, assessmentId: "attempt-1", answers: {} });
  const r = rig({ storage, existing: session("attempt-1", { expires_at: null }) });
  await r.controller.restore();
  assert.equal(r.snapshot().phase, "unavailable");
  assert.match(r.snapshot().error, /timing is unavailable/);
  assert.equal(r.calls.submit.length, 0);
});

test("invalid and foreign session references fail closed", async () => {
  for (const existing of [session("other-id"), session("attempt-1", { profile_id: "another-student" })]) {
    const r = rig({ existing, storage: memoryStorage({ profileId, assessmentId: "attempt-1" }) });
    await r.controller.restore();
    assert.equal(r.snapshot().phase, "unavailable");
    assert.equal(r.snapshot().result, null);
    assert.equal(r.calls.submit.length, 0);
  }
});

test("successful retake replaces the result only after confirmation and resets answers", async () => {
  const r = await started();
  r.controller.selectAnswer("q0", 1);
  await r.controller.submit();
  const oldResult = r.snapshot().result;
  const gate = deferred();
  const start = r.api.start;
  r.api.start = async (...args) => { await gate.promise; return start(...args); };
  const retake = r.controller.startNew();
  await r.controller.startNew();
  assert.equal(r.snapshot().starting, true);
  assert.equal(r.snapshot().result, oldResult);
  assert.equal(r.snapshot().phase, "finished");
  gate.resolve();
  await retake;
  assert.equal(r.snapshot().phase, "running");
  assert.equal(r.snapshot().result, null);
  assert.deepEqual(r.snapshot().answers, {});
  assert.equal(r.calls.start.length, 2);
  assert.equal(r.snapshot().session.assessment_id, "new-2");
});

for (const rejection of [
  error("Transient network failure"),
  error("Please wait before retrying Python", 429, { retryAfterSeconds: 10, nextAllowedAt: stamp(10000) }),
  error("Maximum attempts reached for Python", 429),
  error("Backend unavailable", 503),
]) {
  test("failed retake preserves the finished result: " + rejection.message, async () => {
    const r = await started();
    await r.controller.submit();
    const oldResult = r.snapshot().result;
    r.api.start = async () => { throw rejection; };
    await r.controller.startNew();
    assert.equal(r.snapshot().phase, "finished");
    assert.equal(r.snapshot().result, oldResult);
    assert.equal(r.snapshot().starting, false);
    assert.equal(r.snapshot().error, rejection.message);
  });
}

test("a transient failed retake can be retried successfully", async () => {
  const r = await started();
  await r.controller.submit();
  const start = r.api.start;
  r.api.start = async () => { throw error("Network offline"); };
  await r.controller.startNew();
  r.api.start = start;
  await r.controller.startNew();
  assert.equal(r.snapshot().phase, "running");
  assert.equal(r.snapshot().session.assessment_id, "new-2");
});

test("a malformed retake confirmation cannot erase the previous result", async () => {
  const r = await started();
  await r.controller.submit();
  const original = r.snapshot().result;
  r.api.start = async () => session("malformed", { expires_at: null });
  await r.controller.startNew();
  assert.equal(r.snapshot().result, original);
  assert.equal(r.snapshot().phase, "finished");
  assert.match(r.snapshot().error, /timing is unavailable/);
});

test("cooldown blocks duplicate requests, survives count changes, and clears when elapsed", async () => {
  const r = await started();
  await r.controller.submit();
  let requests = 0;
  r.api.start = async () => { requests++; throw error("Cooldown", 429, { retryAfterSeconds: 10 }); };
  await r.controller.startNew();
  r.controller.configure("Python", 10);
  await r.controller.startNew();
  assert.equal(requests, 1);
  assert.equal(r.snapshot().cooldownSeconds, 10);
  r.setTime(10000);
  await r.controller.tick();
  assert.equal(r.snapshot().cooldownSeconds, 0);
  assert.equal(r.snapshot().error, null);
  await r.controller.startNew();
  assert.equal(requests, 2);
});

test("changing skill clears only that skill's start policy warning", async () => {
  const r = await started();
  await r.controller.submit();
  r.api.start = async () => { throw error("Maximum attempts", 429); };
  await r.controller.startNew();
  assert.equal(r.snapshot().limitReached, true);
  r.controller.configure("SQL", 5);
  assert.equal(r.snapshot().limitReached, false);
  assert.equal(r.snapshot().error, null);
});

test("configuration navigation preserves a completed result for returning", async () => {
  const r = await started();
  await r.controller.submit();
  const original = r.snapshot().result;
  r.controller.configure("Python", 5);
  assert.equal(r.snapshot().result, original);
  r.controller.showResult();
  assert.equal(r.snapshot().phase, "finished");
  assert.equal(r.snapshot().result, original);
});

test("disconnect stops the owned timer and suppresses stale profile completion callbacks", async () => {
  const r = await started();
  const disconnect = r.controller.connect();
  await r.controller.restore();
  const gate = deferred();
  r.api.submit = () => gate.promise;
  const submitting = r.controller.submit();
  disconnect();
  gate.resolve(report(r.snapshot().session));
  await submitting;
  assert.equal(r.unscheduled(), 1);
  assert.deepEqual(r.calls.completed, []);
});

test("a retired controller cannot overwrite a newer active session reference", async () => {
  const r = await started();
  const disconnect = r.controller.connect();
  await r.controller.restore();
  const original = r.snapshot().session;
  const gate = deferred();
  r.api.submit = () => gate.promise;
  const submitting = r.controller.submit();
  // The server accepted the first result, but its response is still in flight.
  const accepted = report(original);
  r.sessions.set(original.assessment_id, { ...original, status: "COMPLETED", result: accepted });
  disconnect();
  const next = createAssessmentController({ profileId, api: r.api, storage: r.storage,
    storageKey, now: () => 0 });
  await next.restore();
  next.configure("SQL", 5);
  await next.startNew();
  const nextId = next.getSnapshot().session.assessment_id;
  gate.resolve(accepted);
  await submitting;
  assert.equal(JSON.parse(r.storage.getItem(storageKey)).assessmentId, nextId);
  assert.notEqual(nextId, original.assessment_id);
});

test("storage failure retains working in-memory answers and warns about refresh", async () => {
  const r = await started({ storage: { getItem: () => null, setItem: () => { throw new Error("Quota full"); } } });
  r.controller.selectAnswer("q0", 2);
  assert.deepEqual(r.snapshot().answers, { q0: 2 });
  assert.match(r.snapshot().storageWarning, /could not be saved/);
});

test("completed duration is absent when authoritative submission timing is unavailable", () => {
  assert.equal(completedDuration(session()), null);
  assert.equal(completedDuration(session("one", { submitted_at: stamp(60000) })), 60);
});

test("storage references are separated by backend and profile identity", () => {
  assert.notEqual(assessmentStorageKey("one", "http://a"), assessmentStorageKey("two", "http://a"));
  assert.notEqual(assessmentStorageKey("one", "http://a"), assessmentStorageKey("one", "http://b"));
});
