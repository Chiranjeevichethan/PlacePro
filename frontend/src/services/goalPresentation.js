const ACTION_CATEGORIES = {
  'edit-profile': 'profile',
  mocktests: 'mock_test',
  companies: 'opportunity',
  prediction: 'preparation',
};

export function goalDraftFromAction(action) {
  const relatedModule = action?.destination === 'edit-profile' ? 'profile' : action?.destination;
  return {
    title: action?.title || '',
    description: action?.description || '',
    category: action?.skill ? 'skill' : ACTION_CATEGORIES[action?.destination] || 'preparation',
    target_date: '',
    priority: action?.priority === 'High' ? 'high' : action?.priority === 'Optional' ? 'low' : 'medium',
    related_module: relatedModule || '',
  };
}

export function goalDraftFromRoadmap(activity) {
  const destination = activity?.steps?.[0]?.destination;
  const relatedModule = destination === 'edit-profile' ? 'profile' : destination || '';
  const category = activity?.skill ? 'skill' : destination === 'mocktests' ? 'mock_test'
    : destination === 'companies' ? 'opportunity' : destination === 'edit-profile' ? 'profile' : 'preparation';
  return {
    title: activity?.title || '',
    description: [activity?.reason, activity?.steps?.length
      ? `Preparation sequence: ${activity.steps.map((step) => step.title).join(' → ')}.` : null].filter(Boolean).join('\n'),
    category,
    target_date: '',
    priority: activity?.priority === 'High' ? 'high' : activity?.priority === 'Optional' ? 'low' : 'medium',
    related_module: relatedModule,
  };
}

export function goalProgressLabel(goal) {
  if (goal?.progress_percentage === null || goal?.progress_percentage === undefined) return 'No milestones yet';
  return `${goal.progress_percentage}% · ${goal.completed_milestone_count} of ${goal.milestone_count} milestones complete`;
}

export function goalDeadlineLabel(goal) {
  if (goal?.deadline_state === 'completed' || goal?.status === 'completed') return 'Completed';
  if (goal?.deadline_state === 'paused' || goal?.status === 'paused') return goal?.target_date ? `Paused · ${goal.target_date}` : 'Paused · no deadline';
  if (goal?.deadline_state === 'today') return `Due today · ${goal.target_date}`;
  if (goal?.deadline_state === 'upcoming') return `Upcoming · ${goal.target_date}`;
  if (goal?.deadline_state === 'overdue') return `Overdue · ${goal.target_date}`;
  if (!goal?.target_date) return 'No target date';
  if (goal.is_overdue) return `Overdue · ${goal.target_date}`;
  if (goal.is_upcoming) return `Upcoming · ${goal.target_date}`;
  return `Target · ${goal.target_date}`;
}

export function milestoneDeadlineLabel(milestone) {
  if (milestone?.deadline_state === 'completed' || milestone?.status === 'completed') return 'Completed';
  if (milestone?.deadline_state === 'today') return 'Due today';
  if (milestone?.deadline_state === 'upcoming') return 'Upcoming';
  if (milestone?.deadline_state === 'overdue' || milestone?.is_overdue) return 'Overdue';
  return 'No deadline';
}
