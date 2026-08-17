# Phase 17 — Skill Assessment Engine

Phase 17 adds a real, evidence-based skill assessment system. A resume
mention is NOT a skill score — a numerical score comes ONLY from an
actual assessment, evaluated server-side.

> **Important limitation:** The assessment score represents performance
> on the PlacePro assessment question bank and is **not a guaranteed
> measure of real-world expertise**. It is not a professionally
> validated psychometric test. We never claim "Python 82 means the
> student is 82% skilled" — we report "Assessment score: 82/100."

---

## 1. Architecture

```
                        ┌─────────────────────────────┐
                        │  question_bank.py           │
                        │  (server-side only)         │
                        └──────────────┬──────────────┘
                                       │
POST /api/assessment/start             │
   profile_id + skill                  │  questions (NO answers)
        └──────────────▶ assessment_service.py ──▶ session (JSON)
POST /api/assessment/{id}/submit                         │
   answers ───────────▶ server-side scoring ◀────────────┘
                                       │
                        verified evidence (source=assessment)
                                       │
                        ┌──────────────▼──────────────┐
                        │  profile.assessment_evidence │
                        │  readiness  (Phase 12 bonus) │
                        │  recommend. (Phase 14 match) │
                        └─────────────────────────────┘
```

The assessment logic is fully separated from the ML pipeline (the Phase
8 model is untouched).

## 2. Question bank

- **12 supported skills:** Python, Java, C, C++, JavaScript, SQL, Data
  Structures, Algorithms, React, Machine Learning, HTML/CSS, Git
- **144 questions** (12 per skill), each with `question_id`, `skill`,
  `topic`, `difficulty`, `question_type` (`mcq`), `question`, `options`,
  `correct_answer`, `explanation`, `points`
- Difficulty points: **EASY = 1, MEDIUM = 2, HARD = 3** (raw score is
  weighted by difficulty, not volume)
- Adding a skill = adding one dict entry to `QUESTION_BANK` (plus its
  name in `SUPPORTED_SKILLS`)
- Reuses the **Phase 12 taxonomy** skill names (no duplicate
  normalization system)

## 3. Scoring

```
raw_score = earned_points / total_points * 100
```

- Fully **server-side** from the stored bank answers — the client sends
  `question_id → answer` text only.
- Response: `skill_score`, `correct`, `total`, `level`,
  `difficulty_breakdown`, `topic_breakdown`.
- The score is a **percentage, not a probability** and not an ML output.

## 4. Difficulty

Every skill covers **EASY / MEDIUM / HARD** questions across multiple
concepts (e.g. Python: variables, functions, collections, exceptions,
OOP, modules, iterators, comprehensions, file handling; SQL: SELECT,
WHERE, JOIN, GROUP BY, HAVING, subqueries, aggregation, window
functions; DSA: arrays, strings, stacks, queues, linked lists, trees,
graphs, sorting, searching, complexity).

## 5. Topic analysis

`topic_breakdown` reports per-topic accuracy (e.g. OOP: 90, Collections:
80, Exceptions: 100, Iterators: 50) — useful, concrete skill-gap input.

## 6. Verification

- **Resume skill:** `source = resume`, `verified = false`
- **Assessment skill:** `source = assessment`, `verified = true`
- **User-entered skill:** `source = user`, verified per the existing
  verification flow
- Assessment evidence is stored **alongside** resume evidence on the
  profile — resume evidence is never overwritten.

## 7. Provenance

Each evidence entry: `{skill, score, level, source: "assessment",
verified: true, assessment_id, attempt, timestamp}`. The combined skill
view (`GET /api/profile/{id}/skills`) shows `resume_detected`,
`user_entered`, `assessment_score`, `assessment_verified` and `level`
per skill — a resume mention and an assessment score can both be
present.

## 8. Attempt limits (configurable)

- `MAX_ATTEMPTS_PER_SKILL = 3`
- `COOLDOWN_HOURS = 24` between attempts of the same skill
- Assessment history, latest score and best score are all recorded
- Repeated attempts cannot inflate readiness: only the **latest** score
  per skill counts, and the bonus is capped (see below)

## 9. APIs

| Endpoint | Purpose |
|----------|---------|
| `POST /api/assessment/start` | `{profile_id, skill, num_questions?}` → session with questions (**no answers**) |
| `POST /api/assessment/{id}/submit` | `{profile_id, answers}` → server-side score + verified evidence |
| `GET /api/assessment/{id}` | Session view (questions only, no answers) |
| `GET /api/profile/{id}/assessments` | Attempt history |
| `GET /api/profile/{id}/skills` | Combined skill view |

Errors: unknown profile → 404, unverified profile → 422, unknown skill →
404, unknown/invalid assessment id → 404, cross-profile submit → 403,
duplicate submit → 409, unknown question id → 400, attempt limit → 429,
cooldown → 429.

## 10. Readiness integration (Phase 12, careful extension)

The readiness formula is **not replaced**. A documented, capped bonus is
added to the `technical_skills` component:

```
bonus = min(5, avg(latest assessment score of skills >= 60) / 100 * 5)
```

- Only scores ≥ 60 (Intermediate+) qualify.
- Only the **latest** score per skill counts (a student who retries and
  scores lower gets the lower score).
- The bonus is **capped at 5 points** and the technical component is
  capped at its documented weight (30).

## 11. Recommendation integration (Phase 14)

Assessed skills become the **primary evidence** for skill matching:

- A required skill **with an assessment** counts as matched only when
  the score ≥ `ASSESSMENT_SATISFIED_MIN_SCORE` (60).
- A required skill **without an assessment** falls back to the verified
  (resume/user) skill set.
- Consequence: a student who lists "SQL" on the resume but scores 0 on
  the SQL assessment no longer satisfies a company's SQL requirement —
  the resume mention alone is not enough once an assessment exists.

## 12. Security

- **Answer keys never leave the server** — start responses strip
  `correct_answer` / `explanation`.
- **Client-submitted scores are never trusted** — everything is
  evaluated server-side from the bank.
- Sessions are validated by ID + ownership (cross-profile submit → 403).
- Assessment evidence is **server-controlled**: verify/update preserve
  the stored evidence and ignore anything the client sends.
- Attempt limits + cooldown prevent unlimited instant retries.
- Assessment IDs are validated (no path traversal); question-bank paths
  are never exposed.

## 13. Limitations

- Not a professionally validated psychometric test; scores reflect
  performance on this question bank only
- 12 skills / 144 questions (extensible, but a modest starting set)
- Single-choice (`mcq`) questions only for now
- No timed assessments yet (`time_limit_minutes` is null)
- No authentication yet (later phase) — profile ownership is by
  `profile_id` in the request body
