import './authFixtures.js';
import test from "node:test";
import assert from "node:assert/strict";
import { API_BASE_URL, startAssessment, submitAssessment, fetchAssessment } from "../src/services/api.js";
import { buildAnswerPayload } from "../src/services/mockTest.js";

const response = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

test("start sends the canonical request and returns server timing unchanged", async (t) => {
  const data = { assessment_id: "test-id", expires_at: "server-deadline", server_now: "server-time" };
  const calls = [];
  t.mock.method(globalThis, "fetch", async (...args) => { calls.push(args); return response(data); });
  assert.deepEqual(await startAssessment("student", "SQL", 5), data);
  assert.equal(calls[0][0], API_BASE_URL + "/api/assessment/start");
  assert.deepEqual(JSON.parse(calls[0][1].body), { profile_id: "student", skill: "SQL", num_questions: 5 });
  assert.equal(calls[0][1].cache, "no-store");
  assert.ok(calls[0][1].signal instanceof AbortSignal);
});

test("answer conversion sends only selected valid answer text, without client scores or timing", async (t) => {
  const questions = [
    { question_id: "a", options: ["Yes", "No"] }, { question_id: "b", options: ["One", "Two"] },
    { question_id: "c", options: ["Three"] }, { question_id: "d", options: ["Four"] },
  ];
  const converted = buildAnswerPayload(questions, { a: 1, b: 99, c: -1, d: "0", unknown: 0 });
  assert.deepEqual(converted, { answers: { a: "No" } });
  let request;
  t.mock.method(globalThis, "fetch", async (_url, options) => { request = options; return response({ skill_score: 20 }); });
  await submitAssessment("test/id", "student", converted.answers);
  assert.deepEqual(JSON.parse(request.body), { profile_id: "student", answers: { a: "No" } });
});

for (const status of [400, 403, 404, 409, 410, 422, 429, 503]) {
  test("submit preserves HTTP " + status + " and the backend diagnostic", async (t) => {
    t.mock.method(globalThis, "fetch", async () => response({ detail: "Backend diagnostic" }, status));
    await assert.rejects(submitAssessment("test", "student", {}), (error) => {
      assert.equal(error.status, status);
      assert.equal(error.message, "Backend diagnostic");
      return true;
    });
  });
}

for (const call of [() => startAssessment("student", "Python", 5), () => submitAssessment("test", "student", {})]) {
  test("start and submit both retain cooldown retry metadata", async (t) => {
    t.mock.method(globalThis, "fetch", async () => response({ detail: "Cooldown", retry_after_seconds: 40,
      next_allowed_at: "2026-11-06T10:00:40Z" }, 429, { "Retry-After": "40" }));
    await assert.rejects(call(), (error) => {
      assert.equal(error.status, 429);
      assert.equal(error.retryAfterSeconds, 40);
      assert.equal(error.nextAllowedAt, "2026-11-06T10:00:40Z");
      return true;
    });
  });
}

test("terminal attempt limit is distinct from a timed cooldown", async (t) => {
  t.mock.method(globalThis, "fetch", async () => response({ detail: "Maximum attempts" }, 429));
  await assert.rejects(startAssessment("student", "Python", 5), (error) => {
    assert.equal(error.retryAfterSeconds, null);
    assert.equal(error.nextAllowedAt, null);
    return true;
  });
});

test("Retry-After header supplies a cooldown when the body lacks timing", async (t) => {
  t.mock.method(globalThis, "fetch", async () => response({ detail: "Wait" }, 429, { "Retry-After": "12" }));
  await assert.rejects(submitAssessment("test", "student", {}), (error) => error.retryAfterSeconds === 12);
});

test("validation details keep their field-specific message", async (t) => {
  t.mock.method(globalThis, "fetch", async () => response({ detail: [{ loc: ["body", "answers"], msg: "Invalid answers" }] }, 422));
  await assert.rejects(submitAssessment("test", "student", {}), /answers: Invalid answers/);
});

for (const name of ["TypeError", "TimeoutError"]) {
  test(name + " is an explicit uncertain network outcome", async (t) => {
    t.mock.method(globalThis, "fetch", async () => { throw Object.assign(new Error("Fixture"), { name }); });
    await assert.rejects(submitAssessment("test", "student", {}), (error) => {
      assert.equal(error.status, null);
      assert.match(error.message, name === "TimeoutError" ? /timed out/ : /connection/);
      return true;
    });
  });
}

test("malformed successful responses are never treated as assessment success", async (t) => {
  t.mock.method(globalThis, "fetch", async () => response([]));
  await assert.rejects(startAssessment("student", "Python", 5), /unexpected response/);
});

test("GET returns the authoritative status and report without substitutions", async (t) => {
  const data = { assessment_id: "test", profile_id: "student", status: "COMPLETED", result: { skill_score: 0 } };
  t.mock.method(globalThis, "fetch", async () => response(data));
  assert.deepEqual(await fetchAssessment("test"), data);
});
