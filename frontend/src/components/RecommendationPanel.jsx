function RecommendationPanel({ prediction }) {
  const probability = Number(prediction?.probability ?? 72);
  const isLikelyPlaced = probability >= 60;

  const recommendations = [
    {
      icon: "💻",
      title: "Improve Coding Skills",
      description:
        "Practice DSA and problem-solving regularly to strengthen your technical profile.",
      priority: "High Priority",
    },
    {
      icon: "🎤",
      title: "Practice Mock Interviews",
      description:
        "Complete mock interviews to improve confidence and communication during placements.",
      priority: "High Priority",
    },
    {
      icon: "🚀",
      title: "Build More Projects",
      description:
        "Create practical projects and maintain a strong GitHub portfolio.",
      priority: "Medium Priority",
    },
    {
      icon: "🎓",
      title: "Strengthen Aptitude",
      description:
        "Practice quantitative, logical reasoning and verbal aptitude questions.",
      priority: "Medium Priority",
    },
  ];

  return (
    <section className="recommendation-panel">
      <div className="recommendation-header">
        <div>
          <span className="recommendation-eyebrow">
            PLACEPRO INSIGHTS
          </span>

          <h2>
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
          <div className="recommendation-item" key={index}>
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

            <div className="recommendation-arrow">
              →
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default RecommendationPanel;