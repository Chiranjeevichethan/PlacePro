/**
 * LearningResourceCard - learning resources for one missing skill.
 * Links use only well-known platforms and open in a new browser tab
 * (target="_blank" with rel="noopener noreferrer").
 */
function LearningResourceCard({ skill, resources = [] }) {
  if (!resources.length) return null;

  return (
    <div className="resource-card">
      <div className="resource-card-header">
        <h3>
          Missing skill: <strong>{skill}</strong>
        </h3>
        <span className="resource-count">
          {resources.length} resource{resources.length > 1 ? "s" : ""}
        </span>
      </div>

      <ul className="resource-list">
        {resources.map((resource) => (
          <li key={resource.url}>
            <a
              href={resource.url}
              target="_blank"
              rel="noopener noreferrer"
              className="resource-link"
            >
              <span className="resource-platform">{resource.platform}</span>
              <svg
                className="resource-external-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default LearningResourceCard;
