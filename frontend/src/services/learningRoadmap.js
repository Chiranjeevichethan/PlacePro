const MOCK_TEST_SKILLS = new Set([
  'python', 'java', 'c', 'c++', 'javascript', 'sql', 'data structures',
  'algorithms', 'react', 'machine learning', 'html/css', 'git',
]);

const priorityRank = { High: 0, Medium: 1, Optional: 2, 'Priority unavailable': 3 };

function supportsMockTest(skill) {
  return MOCK_TEST_SKILLS.has(skill.trim().toLowerCase());
}

/** Turn existing evidence-backed readiness actions into an undated seven-day sequence. */
export function buildLearningRoadmap(view) {
  if (!view || !Array.isArray(view.actions)) {
    return { days: [], additionalActivities: [], activityCount: 0 };
  }

  const actions = view.actions.map((action, index) => ({ action, index }))
    .sort((left, right) => (priorityRank[left.action.priority] ?? 3)
      - (priorityRank[right.action.priority] ?? 3) || left.index - right.index)
    .map(({ action }) => action);

  const activities = actions.map((action) => {
    if (action.skill && action.destination === 'skillgap') {
      const steps = [
        {
          id: `${action.id}-review`,
          title: `Review the ${action.skill} gap`,
          detail: action.description,
          destination: 'skillgap',
          linkLabel: 'Open Skill Gap Analysis',
        },
        {
          id: `${action.id}-prepare`,
          title: action.title,
          detail: action.rationale,
          destination: 'skillgap',
          linkLabel: `Review ${action.skill} guidance`,
        },
      ];

      if (supportsMockTest(action.skill)) {
        steps.push({
          id: `${action.id}-practice`,
          title: `Practise ${action.skill}`,
          detail: `Open Mock Tests and choose ${action.skill} from the available skills. The assessment result is recorded only after the existing test is completed and saved.`,
          destination: 'mocktests',
          linkLabel: 'Open Mock Tests',
        });
        steps.push({
          id: `${action.id}-review`,
          title: 'Review the saved assessment result',
          detail: 'After an assessment result is saved, review its recorded feedback in Performance Analysis. This step does not claim that an assessment has already been completed.',
          destination: 'performance',
          linkLabel: 'Open Performance Analysis',
        });
      }

      return {
        id: `roadmap-${action.id}`,
        sourceActionId: action.id,
        skill: action.skill,
        title: `${action.skill} preparation sequence`,
        priority: action.priority,
        reason: action.rationale,
        steps,
      };
    }

    return {
      id: `roadmap-${action.id}`,
      sourceActionId: action.id,
      title: action.title,
      priority: action.priority,
      reason: action.rationale || action.description,
      steps: [{
        id: `${action.id}-action`,
        title: action.title,
        detail: action.description,
        destination: action.destination,
        linkLabel: action.cta,
      }],
    };
  });

  return {
    days: activities.slice(0, 7).map((activity, index) => ({
      number: index + 1,
      activity,
    })),
    additionalActivities: activities.slice(7),
    activityCount: activities.length,
  };
}
