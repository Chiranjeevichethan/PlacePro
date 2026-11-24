/** Assessment state and delivery coordination. Scores always come from the API. */
export const AUTO_SUBMIT_LEAD_MS = 1000;

export const assessmentStorageKey = (profileId, apiUrl, accountId = null) =>
  `placepro_assessment:${encodeURIComponent(apiUrl)}:${encodeURIComponent(profileId)}${accountId ? ':account:' + encodeURIComponent(accountId) : ''}`;

/** Anchor server UTC to a monotonic clock; browser clock changes cannot add time. */
export function createDeadlineClock(session, receivedAt, requestDurationMs = 0) {
  const created = Date.parse(session.created_at);
  const expires = Date.parse(session.expires_at);
  const serverNow = Date.parse(session.server_now);
  if (![created, expires, serverNow].every(Number.isFinite) || expires <= created) {
    throw new Error("Assessment timing is unavailable. Reload the assessment before continuing.");
  }
  return {
    // Deduct the whole request duration conservatively, including delivery delay.
    deadline: receivedAt + Math.max(0, expires - serverNow - requestDurationMs),
    totalSeconds: (expires - created) / 1000,
  };
}

export const remainingMilliseconds = (clock, now) =>
  clock ? Math.max(0, clock.deadline - now) : 0;

export function completedDuration(session) {
  const created = Date.parse(session.created_at);
  const submitted = Date.parse(session.submitted_at);
  return Number.isFinite(created) && Number.isFinite(submitted) && submitted >= created
    ? Math.round((submitted - created) / 1000)
    : null;
}

const readable = (error) => error?.message || "Unable to process the assessment. Please try again.";

function checkedResult(result, session) {
  if (!result || result.assessment_id !== session.assessment_id || result.skill !== session.skill ||
      !Number.isFinite(result.skill_score) || result.skill_score < 0 || result.skill_score > 100 ||
      !Number.isInteger(result.correct) || !Number.isInteger(result.total) || result.total < 1 ||
      result.correct < 0 || result.correct > result.total || typeof result.level !== "string") {
    throw new Error("The saved assessment result is unavailable. Check the assessment status.");
  }
  return result;
}

function checkedQuestions(session) {
  const questions = session.questions;
  if (!session.assessment_id || typeof session.skill !== "string" || !Array.isArray(questions) ||
      questions.length === 0 || questions.some((q) => !q || typeof q !== "object") ||
      new Set(questions.map((q) => q.question_id)).size !== questions.length ||
      questions.some((q) => !q.question_id || typeof q.question !== "string" ||
        !Array.isArray(q.options) || q.options.length === 0 ||
        q.options.some((option) => typeof option !== "string"))) {
    throw new Error("The assessment service returned invalid questions. Reload the assessment.");
  }
}

function checkedAnswers(questions, answers) {
  return Object.fromEntries((questions ?? []).flatMap((question) => {
    const index = answers?.[question.question_id];
    return Number.isInteger(index) && index >= 0 && index < question.options.length
      ? [[question.question_id, index]] : [];
  }));
}

/** Dependencies are injected so deadline, storage and network regressions need no real data. */
export function createAssessmentController({
  profileId,
  api,
  storageKey,
  storage,
  now = () => performance.now(),
  onCompleted = () => {},
  schedule = (callback) => setInterval(callback, 250),
  unschedule = (id) => clearInterval(id),
}) {
  const listeners = new Set();
  let draft = {};
  let storageWarning = null;
  try {
    storage = storage === undefined ? globalThis.sessionStorage : storage;
    draft = JSON.parse(storage?.getItem(storageKey) || "{}");
    if (!draft || draft.profileId !== profileId || (typeof draft.assessmentId !== "string" && !draft.startIntent)) draft = {};
  } catch {
    draft = {};
    storageWarning = "Answers can only be kept in this open page because browser storage is unavailable.";
  }
  let referenceId = draft.assessmentId ?? null;
  let startIntent = draft.startIntent ?? null;
  if (startIntent && (typeof startIntent.key !== 'string' || !/^[a-f0-9-]{36}$/.test(startIntent.key))) startIntent = null;
  let pending = draft.pending ?? null;
  let clock = null;
  let cooldownDeadline = null;
  let deadlineChecked = false;
  let interval = null;
  let restorePromise = null;
  let notifyCompletion = true;
  const notified = new Set();
  let state = {
    phase: "loading", session: null, result: null, answers: {},
    skill: "Python", count: 25, starting: false, submitting: false, checking: false,
    error: null, errorStatus: null, secondsLeft: 0, totalSeconds: 0,
    cooldownSeconds: 0, nextAllowedAt: null, limitReached: false,
    autoAttempted: Boolean(draft.autoAttempted), autoSubmitted: false,
    locked: Boolean(pending), timeTakenSeconds: null, storageWarning,
  };

  function update(patch) {
    state = { ...state, ...patch };
    listeners.forEach((listener) => listener());
  }

  function persist() {
    // A detached component may still receive a late network response. Its
    // draft was saved before delivery; it must not overwrite a newer owner.
    if ((!referenceId && !startIntent) || !notifyCompletion) return;
    // Never cache a score or evidence. Refresh requires a backend-confirmed result.
    draft = { profileId, assessmentId: referenceId, answers: state.answers,
      autoAttempted: state.autoAttempted, pending, startIntent };
    try {
      if (!storage) throw new Error("No browser storage");
      storage.setItem(storageKey, JSON.stringify(draft));
    } catch {
      if (!state.storageWarning) update({ storageWarning:
        "Keep this page open: your answers could not be saved for a browser refresh." });
    }
  }

  function policyError(error) {
    const seconds = Number(error?.retryAfterSeconds);
    const timed = error?.status === 429 && Number.isFinite(seconds) && seconds > 0;
    cooldownDeadline = timed ? now() + seconds * 1000 : null;
    update({ error: readable(error), errorStatus: error?.status ?? null,
      cooldownSeconds: timed ? Math.ceil(seconds) : 0,
      nextAllowedAt: timed ? error.nextAllowedAt : null,
      limitReached: error?.status === 429 && !timed });
  }

  function complete(result, session) {
    const confirmed = checkedResult(result, session);
    update({ phase: "finished", session, result: confirmed, error: null, errorStatus: null,
      locked: false, autoSubmitted: state.autoAttempted,
      timeTakenSeconds: completedDuration(session) ?? state.timeTakenSeconds });
    pending = null;
    persist();
    if (!notified.has(session.assessment_id)) {
      notified.add(session.assessment_id);
      // Refreshing a profile cannot turn an already-confirmed completion into a failure.
      Promise.resolve().then(() => { if (notifyCompletion) return onCompleted(profileId); }).catch(() => {
        update({ error: "Your result is saved. Refresh Student Profile to reload its assessment evidence." });
      });
    }
  }

  function expired(message = "This assessment has expired. Late answers cannot be scored.") {
    pending = null;
    update({ phase: "expired", result: null, locked: true, secondsLeft: 0,
      error: message, errorStatus: 410 });
    persist();
  }

  function adopt(session, requestStart) {
    if (session.assessment_id !== referenceId || session.profile_id !== profileId) {
      throw new Error("This assessment does not belong to the current student profile.");
    }
    const restoredAnswers = state.session?.assessment_id === referenceId ? state.answers : draft.answers;
    update({ session, skill: session.skill, count: session.total_questions ?? state.count });
    if (session.status === "COMPLETED") {
      complete(session.result, session);
      return;
    }
    if (session.status === "EXPIRED") {
      update({ session });
      expired(session.status_reason || undefined);
      return;
    }
    if (session.status === "SUBMITTING") {
      update({ phase: "running", session, locked: true,
        error: "Your submission is being recovered. Check its status to load the confirmed result." });
      return;
    }
    if (session.status !== "IN_PROGRESS") throw new Error("This assessment is no longer active.");
    checkedQuestions(session);
    const received = now();
    clock = createDeadlineClock(session, received, received - requestStart);
    deadlineChecked = false;
    // An authoritative IN_PROGRESS read confirms no answers were accepted yet.
    pending = null;
    update({ phase: "running", session, result: null,
      skill: session.skill, count: session.questions.length,
      answers: checkedAnswers(session.questions, restoredAnswers),
      locked: false, secondsLeft: Math.ceil(remainingMilliseconds(clock, received) / 1000),
      totalSeconds: clock.totalSeconds });
    persist();
  }

  async function checkStatus(originalError = null) {
    if (!referenceId || state.checking) return;
    update({ checking: true, error: null });
    const requestStart = now();
    try {
      const session = await api.get(referenceId);
      adopt(session, requestStart);
      if (state.phase === "running" && originalError) policyError(originalError);
    } catch (error) {
      if (error?.status === 410) expired(readable(error));
      else update({ phase: state.phase === "loading" || !state.session ? "unavailable" : state.phase, locked: true,
        errorStatus: originalError?.status ?? error?.status ?? null,
        error: originalError
          ? readable(originalError) + " The saved status could not be checked. Please check again."
          : readable(error) });
    } finally {
      update({ checking: false });
    }
  }

  async function restore() {
    if (restorePromise) return restorePromise;
    restorePromise = (async () => {
      try {
        if (!referenceId && api.history) {
          const history = await api.history(profileId);
          if (history.profile_id !== profileId || !Array.isArray(history.assessments)) {
            throw new Error("Assessment history is unavailable. Please try again.");
          }
          referenceId = history.assessments.at(-1)?.assessment_id ?? null;
        }
        if (referenceId) await checkStatus();
        else update({ phase: "setup", error: null });
      } catch (error) {
        update({ phase: "unavailable", error: readable(error) });
      }
    })();
    try { await restorePromise; } finally { restorePromise = null; }
  }

  async function startNew() {
    if (state.starting || state.submitting || state.checking || state.cooldownSeconds > 0 ||
        state.limitReached) return;
    update({ starting: true, error: null, errorStatus: null });
    const requestStart = now();
    try {
      if (!startIntent || startIntent.skill !== state.skill || startIntent.count !== state.count) {
        startIntent = { skill: state.skill, count: state.count, key: crypto.randomUUID() };
      }
      persist(); // Save the intent before delivery, including a lost start response.
      const session = await api.start(profileId, state.skill, state.count, startIntent.key);
      if ((session.profile_id && session.profile_id !== profileId) ||
          (session.status && session.status !== "IN_PROGRESS")) {
        throw new Error("The assessment service did not confirm a new session for this profile.");
      }
      checkedQuestions(session);
      const received = now();
      const nextClock = createDeadlineClock(session, received, received - requestStart);
      // Only a validated successful response replaces the previous completed result/draft.
      referenceId = session.assessment_id;
      startIntent = null;
      pending = null;
      clock = nextClock;
      deadlineChecked = false;
      cooldownDeadline = null;
      update({ phase: "running", session: { ...session, profile_id: profileId, status: "IN_PROGRESS" },
        result: null, answers: {}, locked: false, autoAttempted: false, autoSubmitted: false,
        totalSeconds: clock.totalSeconds,
        secondsLeft: Math.ceil(remainingMilliseconds(clock, received) / 1000),
        timeTakenSeconds: null, cooldownSeconds: 0, nextAllowedAt: null });
      persist();
    } catch (error) {
      policyError(error);
    } finally {
      update({ starting: false });
    }
  }

  async function submit(byTime = false) {
    if (state.phase !== "running" || state.submitting || state.checking || state.starting ||
        state.cooldownSeconds > 0 || state.limitReached) return;
    if (state.locked) { await checkStatus(); return; }
    if (remainingMilliseconds(clock, now()) <= 0) { await checkStatus(); return; }
    const answers = { ...state.answers };
    pending = { answers, byTime, requestId: pending?.requestId || crypto.randomUUID() };
    update({ submitting: true, locked: true, error: null, errorStatus: null,
      autoAttempted: state.autoAttempted || byTime,
      timeTakenSeconds: Math.round(clock.totalSeconds - remainingMilliseconds(clock, now()) / 1000) });
    persist();
    try {
      const result = await api.submit(referenceId, state.session.questions, answers, profileId, pending.requestId);
      complete(result, state.session);
    } catch (error) {
      if (error?.status === 410) expired(readable(error));
      else if (error?.status === 400 || error?.status === 422 || error?.status === 429 || error?.status === 403) {
        pending = null;
        update({ locked: false });
        policyError(error);
        persist();
      } else {
        // 409, lost responses, timeouts and 5xx may follow a committed submission.
        // Reconcile first. No success is shown until GET or POST confirms it.
        await checkStatus(error);
      }
    } finally {
      update({ submitting: false });
    }
  }

  async function retrySubmission() {
    if (state.submitting || state.checking) return;
    await checkStatus();
    if (state.phase === "running" && !state.locked) await submit(state.autoAttempted);
  }

  function tick() {
    const remaining = remainingMilliseconds(clock, now());
    const secondsLeft = Math.ceil(remaining / 1000);
    const cooldownSeconds = cooldownDeadline ? Math.ceil(Math.max(0, cooldownDeadline - now()) / 1000) : 0;
    if (secondsLeft !== state.secondsLeft || cooldownSeconds !== state.cooldownSeconds) {
      update({ secondsLeft, cooldownSeconds });
    }
    if (cooldownDeadline && cooldownSeconds === 0) {
      cooldownDeadline = null;
      update({ error: state.errorStatus === 429 ? null : state.error, errorStatus: null, nextAllowedAt: null });
    }
    if (state.phase !== "running" || state.submitting || state.checking) return;
    if (remaining === 0 && !deadlineChecked) {
      deadlineChecked = true;
      return checkStatus();
    }
    if (remaining > 0 && remaining <= AUTO_SUBMIT_LEAD_MS && !state.autoAttempted && !state.locked) {
      return submit(true);
    }
  }

  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    connect() {
      notifyCompletion = true;
      if (interval === null) interval = schedule(() => { void tick(); });
      void restore();
      return () => { if (interval !== null) unschedule(interval); interval = null; notifyCompletion = false; };
    },
    restore, startNew, submit, retrySubmission, checkStatus, tick,
    selectAnswer(questionId, optionIndex) {
      if (state.phase !== "running" || state.locked || state.submitting || remainingMilliseconds(clock, now()) <= 0) return;
      const next = checkedAnswers(state.session.questions, { ...state.answers, [questionId]: optionIndex });
      update({ answers: next });
      persist();
    },
    configure(skill, count) {
      if (state.starting || state.submitting) return;
      const changedSkill = skill !== state.skill;
      if (changedSkill) cooldownDeadline = null;
      update({ phase: "setup", skill, count,
        ...(changedSkill ? { error: null, errorStatus: null, cooldownSeconds: 0,
          nextAllowedAt: null, limitReached: false } : {}) });
    },
    showResult() { if (state.result) update({ phase: "finished" }); },
  };
}
