import {
  displayCountOrNull,
  displayPercentOrNull,
} from './performanceDisplay.js';

const asArray = (value) => Array.isArray(value) ? value : [];
const textOrNull = (value) => typeof value === 'string' && value.trim() ? value.trim() : null;

function latestPredictionState(summary, history) {
  const latest = history.length ? history[history.length - 1] : null;
  const rawProbability = latest?.placement_probability;
  const probability = displayPercentOrNull(rawProbability, 100);

  return {
    count: displayCountOrNull(summary?.predictions_count),
    label: textOrNull(latest?.prediction),
    probability: probability !== null && probability >= 0 && probability <= 100
      ? probability
      : null,
    current: typeof summary?.latest_is_current === 'boolean'
      ? summary.latest_is_current
      : null,
  };
}

const PRIORITY_ORDER = { High: 0, Medium: 1, Optional: 2, 'Priority unavailable': 3 };

function skillKey(value) {
  return textOrNull(value)?.toLowerCase() ?? null;
}

function gapPriority(gap) {
  if (gap?.priority === 'HIGH') return 'High';
  if (gap?.priority === 'MEDIUM') return 'Medium';
  if (gap?.priority === 'LOW') return 'Optional';
  return 'Priority unavailable';
}

function buildActions(readiness, profileCompleteness, assessments, prediction, companies) {
  const actions = [];
  const missingFields = asArray(profileCompleteness?.missing_fields);
  const completionPercentage = displayPercentOrNull(profileCompleteness?.percentage);
  const assessmentCount = assessments.count;
  const predictionCount = prediction.count;
  const gaps = Array.isArray(readiness?.skill_gaps) ? readiness.skill_gaps : [];
  const gapBySkill = new Map(gaps.map((gap) => [skillKey(gap?.skill), gap]).filter(([skill]) => skill));

  if (missingFields.length > 0 || (completionPercentage !== null && completionPercentage < 100)) {
    actions.push({
      id: 'complete-profile',
      title: 'Complete your student profile',
      description: missingFields.length
        ? `Add the missing information: ${missingFields.join(', ')}.`
        : 'Review your profile and add any missing sections.',
      destination: 'edit-profile',
      cta: 'Review profile',
      priority: 'High',
      rationale: 'The verified profile completeness response reports missing information.',
      followUp: 'Save and confirm your profile. This plan will refresh from the updated completeness response.',
    });
  }

  asArray(readiness?.improvement_plan).forEach((item, index) => {
    const skill = textOrNull(item?.skill);
    const action = textOrNull(item?.action);
    if (!skill || !action) return;
    const gap = gapBySkill.get(skillKey(skill));
    const priority = gap ? gapPriority(gap) : 'Priority unavailable';
    actions.push({
      id: `skill-${skill.toLowerCase()}-${index}`,
      title: action,
      description: textOrNull(item?.reason) || `Review the readiness guidance for ${skill}.`,
      skill,
      destination: 'skillgap',
      cta: `Explore ${skill} resources`,
      priority,
      rationale: gap
        ? `${priority === 'Priority unavailable' ? 'The backend did not provide a recognized priority for this gap.' : `The backend marks this requirement ${gap.priority}.`} A gap means the evidence was not found in the confirmed profile; it does not prove you lack the skill.`
        : 'The backend returned this improvement-plan item without a matching skill-gap priority, so it is kept after ranked actions.',
      followUp: 'Use a listed learning resource or practise this skill. When you return, the plan refreshes from current verified profile and assessment evidence.',
    });
  });

  const latestVerifiedAssessment = asArray(assessments.history).slice().reverse()
    .find((entry) => entry?.verified === true && textOrNull(entry?.skill));
  const weakLevel = ['Beginner', 'Developing'].includes(latestVerifiedAssessment?.level);
  if (weakLevel && !gapBySkill.has(skillKey(latestVerifiedAssessment.skill))) {
    actions.push({
      id: `review-assessment-${skillKey(latestVerifiedAssessment.skill)}`,
      title: `Practise ${latestVerifiedAssessment.skill} again`,
      description: `Your latest verified assessment record is labelled ${latestVerifiedAssessment.level}.`,
      skill: latestVerifiedAssessment.skill,
      destination: 'mocktests',
      cta: 'Practise this skill',
      priority: 'Medium',
      rationale: 'Uses the assessment level returned by the backend; it is a practice suggestion, not a claim about ability.',
      followUp: 'Complete a Mock Test for this area. The recorded assessment history will appear here after you return.',
    });
  }

  if (assessmentCount === 0 && asArray(assessments.history).length === 0) {
    actions.push({
      id: 'first-assessment',
      title: 'Take a practice assessment',
      description: 'There are no assessment records yet. A completed Mock Test will add an actual result to your history.',
      destination: 'mocktests',
      cta: 'Open Mock Tests',
      priority: 'Medium',
      rationale: 'No assessment history is recorded for this verified profile.',
      followUp: 'Complete a Mock Test, then return to review the server-recorded result and refreshed action plan.',
    });
  }

  if (predictionCount === 0 && asArray(prediction.history).length === 0) {
    actions.push({
      id: 'first-prediction',
      title: 'Run a placement estimate',
      description: 'View the separate model estimate available for your confirmed profile.',
      destination: 'prediction',
      cta: 'Open Placement Prediction',
      priority: 'Optional',
      rationale: 'No saved estimate is present in the profile prediction history.',
      followUp: 'Any estimate saved through the existing prediction workflow will remain separate from readiness and assessment results.',
    });
  }

  if (companies.length > 0) {
    actions.push({
      id: 'review-companies',
      title: 'Explore current company recommendations',
      description: 'Review the recommendations currently returned for this profile.',
      destination: 'companies',
      cta: 'Review recommendations',
      priority: 'Optional',
      rationale: 'Company recommendations are available from the existing backend service.',
      followUp: 'Revisit after updating your verified profile or addressing a skill gap; recommendations refresh from the service response.',
    });
  }

  return actions.map((action, index) => ({ action, index }))
    .sort((left, right) => (PRIORITY_ORDER[left.action.priority] ?? PRIORITY_ORDER['Priority unavailable'])
      - (PRIORITY_ORDER[right.action.priority] ?? PRIORITY_ORDER['Priority unavailable']) || left.index - right.index)
    .map(({ action }) => action);
}

function recommendedCompanies(recommendations) {
  const groups = recommendations?.recommendations ?? {};
  const candidates = [...asArray(groups.recommended), ...asArray(groups.eligible)];
  const seen = new Set();

  return candidates.filter((company) => {
    const key = textOrNull(company?.company_id) || textOrNull(company?.company_name);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 3).map((company) => ({
    id: textOrNull(company?.company_id) || company.company_name,
    name: textOrNull(company?.company_name) || 'Company name unavailable',
    eligibility: textOrNull(company?.eligibility_status) || textOrNull(company?.status),
  }));
}

/** Build a view from existing backend evidence; this does not calculate readiness. */
export function buildCareerReadinessView(performance, recommendations) {
  const readiness = performance?.readiness;
  if (performance?.verified !== true || !readiness || typeof readiness !== 'object') return null;

  const summary = performance.summary ?? {};
  const assessmentSummary = summary.assessments ?? summary;
  const predictionSummary = summary.predictions ?? summary;
  const assessmentHistory = asArray(performance.assessment_history);
  const predictionHistory = asArray(performance.prediction_history);
  const profileCompleteness = readiness.profile_completeness ?? null;
  const skillGaps = Array.isArray(readiness.skill_gaps)
    ? readiness.skill_gaps.filter((item) => textOrNull(item?.skill))
    : null;
  const strengths = Array.isArray(readiness.strengths)
    ? readiness.strengths.map((item) => textOrNull(item?.skill)).filter(Boolean)
    : null;
  const skills = asArray(performance.skills)
    .map((entry) => textOrNull(entry?.skill))
    .filter(Boolean);
  const assessmentCount = displayCountOrNull(assessmentSummary?.assessments_count);
  const prediction = latestPredictionState(predictionSummary, predictionHistory);
  const companies = recommendedCompanies(recommendations);
  const verifiedAssessmentHistory = assessmentHistory.filter((entry) => entry?.verified === true);
  const recordedActivity = [
    ...(profileCompleteness?.percentage === 100 && Array.isArray(profileCompleteness?.missing_fields)
      && profileCompleteness.missing_fields.length === 0
      ? [{ id: 'profile-complete', kind: 'Profile', title: 'Profile sections complete', detail: 'The backend reports 100% completeness.' }]
      : []),
    ...verifiedAssessmentHistory.slice(-3).reverse().map((entry) => ({
      id: `assessment-${textOrNull(entry.assessment_id) || `${entry.skill}-${entry.timestamp}`}`,
      kind: 'Assessment',
      title: `Completed assessment: ${textOrNull(entry.skill) || 'Skill unavailable'}`,
      detail: [textOrNull(entry.level), displayPercentOrNull(entry.score) === null
        ? null : `${displayPercentOrNull(entry.score)}%`, textOrNull(entry.timestamp)].filter(Boolean).join(' · ') || 'Verified assessment record.',
    })),
    ...predictionHistory.slice(-2).reverse().map((entry, index) => {
      const recordRevision = displayCountOrNull(entry?.source_revision);
      const currentRevision = displayCountOrNull(performance.source_revision);
      const estimateState = recordRevision === null || currentRevision === null
        ? 'Source revision unavailable'
        : recordRevision === currentRevision ? 'For the current profile revision' : 'For an earlier profile revision';
      return {
        id: `prediction-${textOrNull(entry?.timestamp) || index}`,
        kind: 'Estimate',
        title: 'Saved placement model estimate',
        detail: [textOrNull(entry?.prediction), estimateState].filter(Boolean).join(' · '),
      };
    }),
  ].slice(0, 6);

  return {
    readinessScore: displayPercentOrNull(readiness.readiness_score),
    readinessLevel: textOrNull(readiness.readiness_level),
    profileCompleteness: {
      percentage: displayPercentOrNull(profileCompleteness?.percentage),
      missingFields: Array.isArray(profileCompleteness?.missing_fields)
        ? profileCompleteness.missing_fields.filter((field) => typeof field === 'string')
        : null,
    },
    skillGaps,
    strengths,
    skillsTracked: displayCountOrNull(summary.skills_tracked),
    skillNames: [...new Set(skills)].slice(0, 8),
    assessments: {
      count: assessmentCount,
      averageScore: displayPercentOrNull(assessmentSummary?.average_score),
      latest: assessmentHistory.length ? assessmentHistory[assessmentHistory.length - 1] : null,
      history: assessmentHistory,
    },
    prediction,
    companies,
    actions: buildActions(readiness, profileCompleteness, {
      count: assessmentCount,
      history: assessmentHistory,
    }, { ...prediction, history: predictionHistory }, companies),
    recordedActivity,
    hasAssessmentHistory: assessmentHistory.length > 0,
    hasPredictionHistory: predictionHistory.length > 0,
    hasCompanyRecommendations: companies.length > 0,
  };
}
