import IconMark from "../components/IconMark";
import Logo from "../components/Logo";

const features = [
  {
    icon: "prediction",
    title: "Placement Prediction",
    description:
      "Predicts a student's placement probability from academic, technical, and personal factors.",
  },
  {
    icon: "profile",
    title: "Student Profile Analysis",
    description:
      "Structured profile view of a student's academics, skills, and activities.",
  },
  {
    icon: "performance",
    title: "Performance Analysis",
    description:
      "Visual breakdown of strengths and areas for improvement across performance areas.",
  },
  {
    icon: "improve",
    title: "Personalized Recommendations",
    description:
      "Suggests practical improvements to increase a student's placement chances.",
  },
  {
    icon: "model",
    title: "Machine Learning Based Prediction",
    description:
      "Uses ML classification models trained on the placement dataset.",
  },
];

const steps = [
  {
    step: "01",
    title: "Enter Student Details",
    description:
      "The student fills in academic, technical, and personal information through the placement prediction form.",
  },
  {
    step: "02",
    title: "Inputs Are Validated",
    description:
      "The form validates numerical ranges (CGPA, scores, attendance, hours) before submission.",
  },
  {
    step: "03",
    title: "Prediction Is Generated",
    description:
      "The system analyzes the profile and returns a placement probability. Currently a demo result - the real ML API will replace this.",
  },
  {
    step: "04",
    title: "Recommendations",
    description:
      "Students with lower probability get actionable recommendations to improve their profile.",
  },
];

const stackData = [
  {
    category: "Frontend",
    items: [
      { name: "React", logo: "RE", tone: "react" },
      { name: "Vite", logo: "VI", tone: "vite" },
      { name: "JavaScript (JSX)", logo: "JS", tone: "js" },
      { name: "CSS", logo: "CS", tone: "css" },
    ],
    note: "Single-page application with component-based UI.",
  },
  {
    category: "Machine Learning",
    items: [
      { name: "Python", logo: "PY", tone: "python" },
      { name: "scikit-learn", logo: "SK", tone: "sklearn" },
      { name: "pandas", logo: "PD", tone: "pandas" },
      { name: "NumPy", logo: "NP", tone: "numpy" },
    ],
    note: "Data preprocessing, model training, and evaluation.",
  },
  {
    category: "Data & Visualization",
    items: [
      { name: "matplotlib", logo: "MP", tone: "matplotlib" },
      { name: "seaborn", logo: "SB", tone: "seaborn" },
      { name: "CSV dataset", logo: "CSV", tone: "csv" },
    ],
    note: "Exploratory data analysis and result visualization.",
  },
];

const futureScope = [
  "Live API integration with the trained ML models",
  "Personalized recommendation engine per student",
  "Batch analysis of entire student cohorts for institutions",
  "Model improvements via hyperparameter tuning and more algorithms",
  "Role-specific placement suggestions",
];

function About() {
  return (
    <div className="about-page">
      <div className="about-hero">
        <Logo variant="full" size={76} />
        <p>
          AI-Based Intelligent Student Placement Prediction and Recommendation
          System
        </p>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="info" className="section-title-icon" />
          <span>About PlacePro</span>
        </h2>
        <p>
          PlacePro is an AI-based system that predicts a student's placement
          probability based on academic performance, technical skills, and
          personal attributes. It helps students understand their strengths and
          weaknesses, and provides recommendations to improve their chances of
          getting placed.
        </p>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="objective" className="section-title-icon" />
          <span>Project Objective</span>
        </h2>
        <p>
          The objective of this project is to build an intelligent system that:
        </p>
        <ul className="about-list">
          <li>Analyzes student data using machine learning models</li>
          <li>Predicts whether a student is likely to be placed</li>
          <li>Provides a clean, professional interface for students and staff</li>
          <li>Offers actionable recommendations to improve placement chances</li>
        </ul>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="features" className="section-title-icon" />
          <span>Key Features</span>
        </h2>

        <div className="feature-grid">
          {features.map((feature) => (
            <div key={feature.title} className="feature-card">
              <IconMark name={feature.icon} className="feature-icon" />
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="workflow" className="section-title-icon" />
          <span>How It Works</span>
        </h2>

        <div className="steps-list">
          {steps.map((item) => (
            <div key={item.step} className="step-item">
              <span className="step-number">{item.step}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="model" className="section-title-icon" />
          <span>Machine Learning</span>
        </h2>
        <p>
          The ML pipeline loads the placement dataset, preprocesses it (handling
          missing values, encoding categorical columns, removing data-leakage
          columns), and trains classification models. The models used are:
        </p>

        <ul className="about-list">
          <li>
            <strong>Decision Tree Classifier</strong> - accuracy approximately
            51.26%
          </li>
          <li>
            <strong>Random Forest Classifier</strong> - accuracy approximately
            55.19% (current best model)
          </li>
        </ul>

        <p>
          These accuracy values come from the project's initial model run
          (<code>results.txt</code>). Model performance will continue to improve
          as the dataset and pipeline evolve.
        </p>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="stack" className="section-title-icon" />
          <span>Technology Stack</span>
        </h2>

        <div className="stack-grid">
          {stackData.map((stack) => (
            <div key={stack.category} className="stack-card">
              <h3>{stack.category}</h3>
              <div className="stack-items">
                {stack.items.map((item) => (
                  <span key={item.name} className="stack-chip">
                    <span
                      className={`tech-logo tone-${item.tone}`}
                      aria-hidden="true"
                    >
                      {item.logo}
                    </span>
                    <span>{item.name}</span>
                  </span>
                ))}
              </div>
              <p>{stack.note}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="future" className="section-title-icon" />
          <span>Future Scope</span>
        </h2>

        <ul className="about-list">
          {futureScope.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="about-section">
        <h2>
          <IconMark name="team" className="section-title-icon" />
          <span>Project Team</span>
        </h2>

        <div className="team-grid">
          <div className="team-card">
            <div className="team-avatar">B</div>
            <h3>Bhargav</h3>
            <p>Frontend Developer</p>
            <span>Team Member 1</span>
          </div>

          <div className="team-card">
            <div className="team-avatar">?</div>
            <h3>Team Member 2</h3>
            <p>Backend & ML Developer</p>
            <span>Team Member 2</span>
          </div>

          <div className="team-card">
            <div className="team-avatar">?</div>
            <h3>Team Member 3</h3>
            <p>ML & Data Analysis</p>
            <span>Team Member 3</span>
          </div>

          <div className="team-card">
            <div className="team-avatar">?</div>
            <h3>Team Member 4</h3>
            <p>Testing & Documentation</p>
            <span>Team Member 4</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default About;
