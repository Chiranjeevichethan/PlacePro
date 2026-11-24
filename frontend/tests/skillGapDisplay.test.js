import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { resolveSkillGapDisplay } from "../src/services/skillGapDisplay.js";

const readiness = ({ gaps = [], missingFields = [], percentage = 100 } = {}) => ({
  skill_gaps: gaps,
  profile_completeness: { percentage, missing_fields: missingFields },
});

test("one or more backend gaps remain available for existing recommendations", () => {
  const view = resolveSkillGapDisplay({
    readiness: readiness({ gaps: [{ skill: "Python" }, { skill: "SQL" }] }),
  });

  assert.equal(view.state, "ready");
  assert.deepEqual(view.missingSkills, ["Python", "SQL"]);
  assert.equal(view.hasNoGaps, false);
  assert.equal(view.emptyMessage, null);
});

test("a complete profile with no reported gaps gets a qualified positive message", () => {
  const view = resolveSkillGapDisplay({ readiness: readiness() });

  assert.equal(view.state, "ready");
  assert.equal(view.hasNoGaps, true);
  assert.equal(view.profileIncomplete, false);
  assert.match(view.emptyMessage, /currently available in your profile/i);
  assert.match(view.emptyMessage, /does not mean every skill has been mastered/i);
});

test("no reported gaps on an incomplete profile are explicitly qualified", () => {
  const view = resolveSkillGapDisplay({
    readiness: readiness({ missingFields: ["projects"], percentage: 88 }),
  });

  assert.equal(view.state, "ready");
  assert.equal(view.hasNoGaps, true);
  assert.equal(view.profileIncomplete, true);
  assert.match(view.emptyMessage, /Some profile sections still need information/i);
});

test("incomplete profiles with gaps retain gap results and an incomplete marker", () => {
  const view = resolveSkillGapDisplay({
    readiness: readiness({ gaps: [{ skill: "Python" }], missingFields: ["skills"], percentage: 75 }),
  });

  assert.equal(view.state, "ready");
  assert.deepEqual(view.missingSkills, ["Python"]);
  assert.equal(view.profileIncomplete, true);
  assert.equal(view.hasNoGaps, false);
});

test("loading and error states take precedence over empty-gap messaging", () => {
  assert.deepEqual(resolveSkillGapDisplay({ readiness: readiness(), loading: true }), { state: "loading" });
  assert.deepEqual(resolveSkillGapDisplay({ readiness: readiness(), error: "Unavailable" }), {
    state: "error",
    error: "Unavailable",
  });
});

test("missing completeness or malformed gaps are unavailable, not zero gaps", () => {
  assert.equal(resolveSkillGapDisplay({ readiness: { skill_gaps: [] } }).state, "unavailable");
  assert.equal(resolveSkillGapDisplay({ readiness: readiness({ gaps: [null] }) }).state, "unavailable");
  assert.equal(resolveSkillGapDisplay({ readiness: null }).state, "unavailable");
});

test("Skill Gap Analysis wires loading, error, retry and accessible no-gap output", () => {
  const source = readFileSync(new URL("../src/pages/SkillGapAnalysis.jsx", import.meta.url), "utf8");
  assert.match(source, /view\.state === "loading"/);
  assert.match(source, /view\.state === "error"/);
  assert.match(source, /view\.state === "unavailable"/);
  assert.match(source, /view\.state === "ready"/);
  assert.match(source, /onClick=\{refetch\}/);
  assert.match(source, /view\.hasNoGaps[\s\S]*?role="status"/);
  assert.match(source, /getLearningResources\(skill\)/);
  assert.match(source, /<LearningResourceCard/);
});
