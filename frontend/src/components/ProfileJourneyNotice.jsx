import { studentJourney } from '../services/studentJourney.js';

export default function ProfileJourneyNotice({ profile, completion, onCreate, onReview }) {
  const next = studentJourney(profile, completion);
  if (next.stage === 'ready') return null;
  return <section className="journey-notice" aria-label="Your next step">
    <div><span className="journey-eyebrow">YOUR NEXT STEP</span>
      <h2>{next.title}</h2><p>{next.detail}</p>
      {next.missing.length > 0 && <p className="journey-missing">Missing: {next.missing.join(', ')}.</p>}
    </div>
    <button type="button" className="dash-btn primary" onClick={next.stage === 'empty' ? onCreate : () => onReview(next.stage)}>{next.action}</button>
  </section>;
}
