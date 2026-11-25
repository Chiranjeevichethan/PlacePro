function RecommendationPanel({ prediction, onNavigate }) {
  const probability = Number(prediction?.probability ?? 72);
  const isLikelyPlaced = probability >= 60;

  /* Each card navigates to an existing in-app page via the shared page
     state in App.jsx (the app's only routing mechanism — no router lib).
     All destinations map to real pages rendered in App.jsx. */
  const recommendations = [
    {
      icon: "💻",
      title: "Improve Coding Skills",
      description:
        "Practice DSA and problem-solving regularly to strengthen your technical profile.",
      priority: "High Priority",
      /* No dedicated coding-practice page exists; the closest real
         feature is the skill-gap analysis over the student's strengths.
         Mock Tests also offers Data Structures / Algorithms assessments. */
      destination: "skillgap",
      ariaLabel: "Open Skill Gap Analysis to strengthen coding skills",
    },
    {
      icon: "🎤",
      title: "Practice Mock Interviews",
      description:
        "Complete mock interviews to improve confidence and communication during placements.",
      priority: "High Priority",
      destination: "mocktests",
      ariaLabel: "Open Mock Tests to practice assessment questions",
    },
    {
      icon: "🚀",
      title: "Build More Projects",
      description:
        "Create practical projects and maintain a strong GitHub portfolio.",
      priority: "Medium Priority",
      /* No project hub exists; the profile page is where the student
         maintains projects and GitHub repository details. */
      destination: "profile",
      ariaLabel: "Open Student Profile to maintain projects and GitHub links",
    },
    {
      icon: "🎓",
      title: "Strengthen Aptitude",
      description:
        "Practice quantitative, logical reasoning and verbal aptitude questions.",
      priority: "Medium Priority",
      destination: "mocktests",
      ariaLabel: "Open Mock Tests to strengthen aptitude",
    },
  ];

  return (
    <section
      className="recommendation-panel"
      aria-labelledby="recommendation-heading"
    >
      <div className="recommendation-header">
        <div>
          <span className="recommendation-eyebrow">
            PLACEPRO INSIGHTS
          </span>

          <h2 id="recommendation-heading">
            {isLikelyPlaced
              ? "You're on the right track 🚀"
              : "Let's improve your placement readiness 🚀"}
          </h2>

          <p>
            Based on your current profile, here are some areas that can
            help improve your placement readiness.
          </p>
        </div>

        <div
          className={`readiness-badge ${
            isLikelyPlaced ? "positive" : "warning"
          }`}
        >
          {isLikelyPlaced ? "Good Readiness" : "Needs Improvement"}
        </div>
      </div>

      <div className="recommendation-list">
        {recommendations.map((item, index) => (
          <button
            className="recommendation-item"
            key={index}
            type="button"
            onClick={() => onNavigate(item.destination)}
            aria-label={item.ariaLabel}
          >
            <div className="recommendation-icon">
              {item.icon}
            </div>

            <div className="recommendation-content">
              <div className="recommendation-title-row">
                <h3>{item.title}</h3>

                <span className="priority-badge">
                  {item.priority}
                </span>
              </div>

              <p>{item.description}</p>
            </div>

            <div className="recommendation-arrow" aria-hidden="true">
              →
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

export default RecommendationPanel;