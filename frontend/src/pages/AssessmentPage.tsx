import { useMemo, useState } from "react";
import { assessmentApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { ProgressBar, ProgressRing } from "../components/ui";
import { EmptyState } from "../components/ui/StateBox";
import { useToast } from "../components/ui/Toast";
import {
  ASSESSMENT_COOLDOWN_HOURS,
  ASSESSMENT_MAX_ATTEMPTS,
  ASSESSMENT_SKILLS,
} from "../config/demo";
import { useApi } from "../hooks/useApi";
import type {
  AssessmentHistoryEntry,
  StartAssessmentResponse,
  SubmitAssessmentResponse,
} from "../types";
import { formatDate, humanize } from "../utils/format";

type Phase =
  | { kind: "select" }
  | { kind: "taking"; session: StartAssessmentResponse }
  | { kind: "result"; result: SubmitAssessmentResponse; skill: string };

export function AssessmentPage() {
  return (
    <ProfileGate requireVerified>
      {({ profileId }) => <AssessmentContent profileId={profileId} />}
    </ProfileGate>
  );
}

function AssessmentContent({ profileId }: { profileId: string }) {
  const { data: history, refetch: refetchHistory } = useApi(() =>
    assessmentApi.history(profileId),
  );
  const [phase, setPhase] = useState<Phase>({ kind: "select" });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [current, setCurrent] = useState(0);
  const [starting, setStarting] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { notify } = useToast();

  const attemptsBySkill = useMemo(() => {
    const map: Record<string, AssessmentHistoryEntry[]> = {};
    for (const a of history?.assessments ?? []) {
      (map[a.skill] ??= []).push(a);
    }
    return map;
  }, [history]);

  const latestBySkill = useMemo(() => {
    const map: Record<string, AssessmentHistoryEntry> = {};
    for (const a of history?.assessments ?? []) {
      const prev = map[a.skill];
      if (!prev || a.attempt > prev.attempt) map[a.skill] = a;
    }
    return map;
  }, [history]);

  async function start(skill: string) {
    setStarting(skill);
    setError(null);
    try {
      const session = await assessmentApi.start(profileId, skill);
      setAnswers({});
      setCurrent(0);
      setPhase({ kind: "taking", session });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the assessment.");
    } finally {
      setStarting(null);
    }
  }

  async function submit() {
    if (phase.kind !== "taking") return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await assessmentApi.submit(phase.session.assessment_id, profileId, answers);
      setPhase({ kind: "result", result, skill: phase.session.skill });
      void refetchHistory();
      notify("Assessment submitted — verified evidence recorded.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setPhase({ kind: "select" });
    setError(null);
  }

  const answeredCount = Object.keys(answers).length;

  return (
    <div className="page">
      <PageHeader
        title="Skill Assessment"
        subtitle={
          <>
            Real, evidence-based skill assessments (Phase 17). Scores come from
            an actual assessment evaluated server-side — a resume mention is not
            a score. Answer keys never leave the server.
          </>
        }
      />

      {error && <div className="notice notice-danger mb-16">{error}</div>}

      {phase.kind === "select" && (
        <SkillPicker
          skills={ASSESSMENT_SKILLS}
          attemptsBySkill={attemptsBySkill}
          latestBySkill={latestBySkill}
          onStart={(s) => void start(s)}
          starting={starting}
        />
      )}

      {phase.kind === "taking" && (
        <TakingView
          session={phase.session}
          answers={answers}
          setAnswers={setAnswers}
          current={current}
          setCurrent={setCurrent}
          answeredCount={answeredCount}
          submitting={submitting}
          onSubmit={() => void submit()}
          onCancel={reset}
        />
      )}

      {phase.kind === "result" && (
        <ResultView result={phase.result} skill={phase.skill} onDone={reset} />
      )}

      <Card title="Assessment History" className="mt-16">
        {history?.assessments?.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Skill</th>
                  <th>Score</th>
                  <th>Level</th>
                  <th>Attempt</th>
                  <th>Date</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {[...history.assessments].reverse().map((a) => (
                  <tr key={a.assessment_id}>
                    <td><strong>{a.skill}</strong></td>
                    <td>{a.score.toFixed(1)}</td>
                    <td><Badge tone={scoreTone(a.score)}>{a.level}</Badge></td>
                    <td>{a.attempt}/{ASSESSMENT_MAX_ATTEMPTS}</td>
                    <td className="muted small">{formatDate(a.timestamp)}</td>
                    <td><Badge tone="success">verified ✓</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="📝" title="No assessments yet">
            <p className="small">
              Pick a skill above to take your first assessment. You get up to{" "}
              {ASSESSMENT_MAX_ATTEMPTS} attempts per skill with a{" "}
              {ASSESSMENT_COOLDOWN_HOURS}-hour cooldown between attempts.
            </p>
          </EmptyState>
        )}
      </Card>
    </div>
  );
}

// ---------- Skill picker ----------

function SkillPicker({
  skills,
  attemptsBySkill,
  latestBySkill,
  onStart,
  starting,
}: {
  skills: string[];
  attemptsBySkill: Record<string, AssessmentHistoryEntry[]>;
  latestBySkill: Record<string, AssessmentHistoryEntry>;
  onStart: (skill: string) => void;
  starting: string | null;
}) {
  return (
    <div className="grid grid-3">
      {skills.map((skill) => {
        const attempts = attemptsBySkill[skill] ?? [];
        const latest = latestBySkill[skill];
        const maxed = attempts.length >= ASSESSMENT_MAX_ATTEMPTS;
        return (
          <Card key={skill} className="rec-card">
            <div className="rec-header">
              <span className="rec-company">{skill}</span>
              {latest && (
                <Badge tone={scoreTone(latest.score)}>{latest.score.toFixed(0)}</Badge>
              )}
            </div>
            <div className="rec-meta">
              {attempts.length
                ? `${attempts.length}/${ASSESSMENT_MAX_ATTEMPTS} attempts used`
                : "Not assessed yet"}
            </div>
            {latest && (
              <ProgressBar
                value={latest.score}
                tone={scoreTone(latest.score)}
              />
            )}
            <button
              className="btn btn-sm"
              disabled={maxed || starting !== null}
              onClick={() => onStart(skill)}
            >
              {maxed ? "Limit reached" : starting === skill ? "Starting…" : latest ? "Retake" : "Start assessment"}
            </button>
            {maxed && (
              <div className="small muted">
                Max {ASSESSMENT_MAX_ATTEMPTS} attempts reached; {ASSESSMENT_COOLDOWN_HOURS}-h cooldown applies.
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ---------- Taking view ----------

function TakingView({
  session,
  answers,
  setAnswers,
  current,
  setCurrent,
  answeredCount,
  submitting,
  onSubmit,
  onCancel,
}: {
  session: StartAssessmentResponse;
  answers: Record<string, string>;
  setAnswers: (a: Record<string, string>) => void;
  current: number;
  setCurrent: (n: number) => void;
  answeredCount: number;
  submitting: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const question = session.questions[current];
  const selected = answers[question.question_id];

  function choose(option: string) {
    setAnswers({ ...answers, [question.question_id]: option });
  }

  return (
    <Card
      title={`${session.skill} — Attempt ${session.attempt}`}
      actions={
        <button className="btn btn-sm btn-ghost" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
      }
    >
      <div className="flex-between mb-8">
        <span className="small muted">
          Question {current + 1} of {session.questions.length}
        </span>
        <span className="small muted">{answeredCount} answered</span>
      </div>
      <ProgressBar value={((current + (selected ? 1 : 0)) / session.questions.length) * 100} />

      <div className="flex mt-16" style={{ gap: 10 }}>
        <Badge tone={question.difficulty === "EASY" ? "success" : question.difficulty === "MEDIUM" ? "warning" : "danger"}>
          {question.difficulty}
        </Badge>
        <Badge tone="info">{question.topic}</Badge>
        <Badge tone="neutral">MCQ</Badge>
      </div>

      <h4 className="mt-16">{question.question}</h4>

      <div className="mt-8">
        {question.options.map((option) => (
          <button
            key={option}
            className={`assessment-option ${selected === option ? "selected" : ""}`}
            onClick={() => choose(option)}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="form-actions">
        <button
          className="btn"
          disabled={current === 0}
          onClick={() => setCurrent(current - 1)}
        >
          ← Previous
        </button>
        {current < session.questions.length - 1 ? (
          <button className="btn btn-primary" onClick={() => setCurrent(current + 1)}>
            Next →
          </button>
        ) : (
          <button
            className="btn btn-primary"
            disabled={answeredCount < session.questions.length || submitting}
            onClick={onSubmit}
          >
            {submitting ? "Submitting…" : "Submit assessment"}
          </button>
        )}
      </div>
      {answeredCount < session.questions.length && (
        <p className="small muted">
          Answer all questions before submitting ({answeredCount}/{session.questions.length} answered).
        </p>
      )}
    </Card>
  );
}

// ---------- Result view ----------

function ResultView({
  result,
  skill,
  onDone,
}: {
  result: SubmitAssessmentResponse;
  skill: string;
  onDone: () => void;
}) {
  return (
    <Card title={`${skill} — Result`}>
      <div className="flex" style={{ gap: 20, alignItems: "center" }}>
        <ProgressRing
          value={result.skill_score}
          caption="score"
          tone={scoreTone(result.skill_score)}
        />
        <div className="grow">
          <h4 className="mt-0">
            <Badge tone={scoreTone(result.skill_score)}>{result.level}</Badge>
          </h4>
          <p className="small">
            {result.correct} of {result.total} correct · Attempt {result.attempt}
          </p>
          <p className="small muted">{result.message}</p>
        </div>
      </div>

      <div className="grid grid-2 mt-16">
        <div>
          <h4 className="mt-0">By difficulty</h4>
          {Object.entries(result.difficulty_breakdown).map(([diff, v]) => (
            <div className="breakdown-row" key={diff}>
              <div className="bd-head">
                <span className="bd-label">{humanize(diff)}</span>
                <span className="bd-value">{v.toFixed(0)}%</span>
              </div>
              <ProgressBar value={v} tone={v >= 60 ? "success" : "warning"} />
            </div>
          ))}
        </div>
        <div>
          <h4 className="mt-0">By topic</h4>
          {Object.entries(result.topic_breakdown).map(([topic, v]) => (
            <div className="breakdown-row" key={topic}>
              <div className="bd-head">
                <span className="bd-label">{topic}</span>
                <span className="bd-value">{v.toFixed(0)}%</span>
              </div>
              <ProgressBar value={v} tone={v >= 60 ? "success" : "warning"} />
            </div>
          ))}
          {!Object.keys(result.topic_breakdown).length && (
            <p className="muted small">No topic data.</p>
          )}
        </div>
      </div>

      <div className="form-actions">
        <button className="btn btn-primary" onClick={onDone}>Back to skills</button>
      </div>
    </Card>
  );
}

function scoreTone(score: number): "success" | "warning" | "danger" {
  if (score >= 60) return "success";
  if (score >= 40) return "warning";
  return "danger";
}
