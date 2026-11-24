import './authFixtures.js';
import test from "node:test";
import assert from "node:assert/strict";
import { fetchStudentReadiness, fetchPlacementSummary, fetchPerformance,
  fetchCompanyRecommendations, fetchSkillsView } from "../src/services/api.js";

const response = (data) => new Response(JSON.stringify(data), {
  headers: { "Content-Type": "application/json" },
});
const readiness = (score, level) => ({ profile_id: "student", readiness_score: score,
  readiness_level: level, readiness_breakdown: { technical_skills: 12.7,
    projects: 16, internships: 10, certifications: 0, communication: 0, profile_completeness: 12 },
  skill_gaps: [{ skill: "Python OR Java OR C++", category: "Programming", priority: "HIGH",
    evidence_status: "INSUFFICIENT", reason: "Latest verified assessment is below 60" }],
  strengths: [], improvement_plan: [], profile_completeness: { percentage: 62, missing_fields: [] },
});

for (const [score, level] of [[39.5, "Needs Improvement"], [59.5, "Developing"],
  [74.5, "Placement Ready"], [89.5, "Strong"], [100, "Highly Ready"]]) {
  test(`readiness keeps fractional score ${score}, backend label and evidence reason`, async (t) => {
    const body = readiness(score, level);
    t.mock.method(globalThis, "fetch", async () => response(body));
    assert.deepEqual(await fetchStudentReadiness("student"), body);
  });
}

for (const score of [null, undefined, "60", -1, 101, NaN, Infinity]) {
  test(`missing or invalid readiness ${String(score)} is rejected without a zero substitute`, async (t) => {
    t.mock.method(globalThis, "fetch", async () => response(readiness(score, "Developing")));
    await assert.rejects(fetchStudentReadiness("student"), /unexpected response/);
  });
}

test("summary, performance and recommendation consumers preserve the same fractional readiness", async (t) => {
  const analysis = readiness(50.7, "Developing");
  const summary = { ...analysis, ready_for_prediction: false, placement_probability: null };
  const performance = { summary: { readiness_score: 50.7 }, readiness: analysis, skills: [] };
  const recommendations = { profile_id: "student", recommendations: { incomplete: [{
    readiness_score: 50.7, readiness_level: "Developing", eligibility_status: "INCOMPLETE",
    skill_match: { required_missing: ["Python"], required_matched: ["SQL"] },
  }] } };
  const responses = [summary, performance, recommendations];
  t.mock.method(globalThis, "fetch", async () => response(responses.shift()));
  assert.deepEqual(await fetchPlacementSummary("student"), summary);
  assert.deepEqual(await fetchPerformance("student"), performance);
  assert.deepEqual(await fetchCompanyRecommendations("student"), recommendations);
});

for (const [score, status, verified] of [[null, "MISSING", false], [0, "INSUFFICIENT", true],
  [59.5, "INSUFFICIENT", true], [74.5, "SATISFIED", true], [null, "UNCONFIRMED", false]]) {
  test(`skills view preserves ${status} evidence and nullable score`, async (t) => {
    const body = { profile_id: "student", skills: [{ skill: "Python", assessment_score: score,
      assessment_verified: verified, evidence_status: status, profile_confirmed: false,
      evidence_sources: verified ? ["assessment"] : [],
      assessment_timestamp: verified ? "2026-11-07T00:00:00Z" : null }] };
    t.mock.method(globalThis, "fetch", async () => response(body));
    assert.deepEqual(await fetchSkillsView("student"), body);
  });
}
