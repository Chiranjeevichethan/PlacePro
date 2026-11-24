import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  displayCountOrNull,
  displayIntegerOrNull,
  displayNumberOrNull,
  displayPercentOrNull,
} from "../src/services/performanceDisplay.js";

test("actual zero remains zero for counts and numeric displays", () => {
  assert.equal(displayNumberOrNull(0), 0);
  assert.equal(displayCountOrNull(0), 0);
  assert.equal(displayPercentOrNull(0), 0);
});

test("null, undefined, empty and whitespace-only values stay unavailable", () => {
  for (const value of [null, undefined, "", "   "]) {
    assert.equal(displayNumberOrNull(value), null);
    assert.equal(displayCountOrNull(value), null);
    assert.equal(displayPercentOrNull(value), null);
  }
});

test("valid numeric strings are parsed consistently for counts, integers and percentages", () => {
  assert.equal(displayNumberOrNull(" 12.5 "), 12.5);
  assert.equal(displayCountOrNull("3"), 3);
  assert.equal(displayCountOrNull("0"), 0);
  assert.equal(displayIntegerOrNull("2"), 2);
  assert.equal(displayPercentOrNull("0.756", 100), 76);
});

test("invalid, non-finite and fractional count values are not displayed as zero", () => {
  for (const value of ["not a number", "Infinity", NaN, Infinity, -Infinity, true]) {
    assert.equal(displayNumberOrNull(value), null);
  }
  assert.equal(displayCountOrNull("1.5"), null);
  assert.equal(displayCountOrNull(-1), null);
  assert.equal(displayIntegerOrNull("1.5"), null);
});

test("Performance Analysis renders unavailable counts explicitly while preserving valid zero", () => {
  const source = readFileSync(new URL("../src/pages/PerformanceAnalysis.jsx", import.meta.url), "utf8");
  assert.equal((source.match(/=== null \? "Not available" : (?:predictionsCount|assessmentsCount|skillsAssessed)/g) ?? []).length, 3);
  assert.match(source, /const predictionsCount = displayCountOrNull\(summary\.predictions_count\)/);
  assert.match(source, /const assessmentsCount = displayCountOrNull\(summary\.assessments_count\)/);
  assert.match(source, /const skillsAssessed = displayCountOrNull\(summary\.skills_assessed\)/);
});
