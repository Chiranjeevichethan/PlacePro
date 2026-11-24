import { useState } from 'react';
import { buildLearningRoadmap } from '../services/learningRoadmap.js';

function ActivityCard({ activity, onNavigate, onEditProfile }) {
  return (
    <article className="learning-activity-card">
      <div className="learning-activity-heading">
        <div>
          <span className={`career-priority-badge ${activity.priority === 'Priority unavailable' ? 'unranked' : activity.priority.toLowerCase()}`}>
            {activity.priority}
          </span>
          <h3>{activity.title}</h3>
        </div>
      </div>
      <p className="learning-activity-reason"><strong>Why this is recommended:</strong> {activity.reason}</p>
      <ol className="learning-step-list">
        {activity.steps.map((step, index) => (
          <li key={step.id}>
            <span className="learning-step-number" aria-hidden="true">{index + 1}</span>
            <div>
              <h4>{step.title}</h4>
              <p>{step.detail}</p>
              <button type="button" className="dashboard-action-link" onClick={() => {
                if (step.destination === 'edit-profile') onEditProfile();
                else onNavigate(step.destination);
              }}>
                {step.linkLabel} <span aria-hidden="true">→</span>
              </button>
            </div>
          </li>
        ))}
      </ol>
    </article>
  );
}

export default function LearningRoadmap({ view, roadmap: suppliedRoadmap, onNavigate, onEditProfile }) {
  const roadmap = suppliedRoadmap ?? buildLearningRoadmap(view);
  const [selectedDay, setSelectedDay] = useState(0);
  const activeDay = roadmap.days[selectedDay] ?? roadmap.days[0] ?? null;

  return (
    <section className="career-readiness-section learning-roadmap" aria-labelledby="learning-roadmap-title">
      <div className="career-section-heading">
        <div>
          <span className="career-eyebrow">PERSONALIZED PREPARATION · NO ARTIFICIAL DEADLINES</span>
          <h2 id="learning-roadmap-title">Learning roadmap</h2>
        </div>
        <button type="button" className="dashboard-action-link" onClick={() => onNavigate('skillgap')}>
          Review skill gaps <span aria-hidden="true">→</span>
        </button>
      </div>
      <p className="career-planner-intro">
        This undated sequence is built from your current backend skill-gap priorities and action plan. Day numbers show order only; they are not calendar dates or scheduled appointments. No time estimates are shown because the available recommendations do not include supported durations.
      </p>

      {roadmap.activityCount === 0 ? (
        <div className="learning-roadmap-empty" role="status">
          <h3>No roadmap activities are available yet</h3>
          <p>The current verified response contains no specific actions to sequence. Your recorded progress remains available below, and this roadmap refreshes when you return after the underlying profile or assessment records change.</p>
          <button type="button" className="dash-btn secondary" onClick={() => onNavigate('performance')}>Review Performance Analysis</button>
        </div>
      ) : (
        <>
          <div className="learning-week" aria-label="Recommended preparation sequence for the next seven activity days">
            {Array.from({ length: 7 }, (_, index) => {
              const day = roadmap.days[index];
              return (
                <button
                  key={index}
                  type="button"
                  className={`learning-day-choice ${day && activeDay?.number === day.number ? 'is-selected' : ''}`}
                  aria-pressed={Boolean(day && activeDay?.number === day.number)}
                  disabled={!day}
                  onClick={() => setSelectedDay(index)}
                >
                  <span>Day {index + 1}</span>
                  <strong>{day ? day.activity.title : 'No activity'}</strong>
                </button>
              );
            })}
          </div>
          {activeDay && (
            <div className="learning-daily-view" aria-live="polite" aria-atomic="true">
              <div className="learning-daily-heading">
                <div><span className="career-eyebrow">{activeDay.number === 1 ? "TODAY'S RECOMMENDED SEQUENCE" : `RECOMMENDED SEQUENCE · DAY ${activeDay.number}`}</span><h3>Day {activeDay.number}</h3></div>
                <span className="career-data-note">{activeDay.activity.steps.length} preparation step{activeDay.activity.steps.length === 1 ? '' : 's'}</span>
              </div>
              <ActivityCard activity={activeDay.activity} onNavigate={onNavigate} onEditProfile={onEditProfile} />
            </div>
          )}
          {roadmap.additionalActivities.length > 0 && (
            <div className="learning-additional" aria-labelledby="learning-additional-title">
              <h3 id="learning-additional-title">Additional priority-backed activities</h3>
              <p>These recommendations follow the seven-day overview in the same evidence-based order.</p>
              <ul>
                {roadmap.additionalActivities.map((activity) => (
                  <li key={activity.id}>
                    <span className={`career-priority-badge ${activity.priority === 'Priority unavailable' ? 'unranked' : activity.priority.toLowerCase()}`}>{activity.priority}</span>
                    <span>{activity.title}</span>
                    <button type="button" className="dashboard-action-link" onClick={() => {
                      const firstStep = activity.steps[0];
                      if (firstStep.destination === 'edit-profile') onEditProfile();
                      else onNavigate(firstStep.destination);
                    }}>{activity.steps[0].linkLabel} <span aria-hidden="true">→</span></button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      <p className="career-data-note">Opening a module does not mark work complete. Progress is shown only when the existing server records confirm profile completeness, assessment results, or saved estimates.</p>
    </section>
  );
}
