/**
 * PlacePro demo data for company recommendations, skill gap analysis, and
 * learning resources.
 *
 * IMPORTANT: All of this is DEMO data. There is no recommendation backend or
 * ML model behind these values yet. Matching is a simple transparent
 * calculation (see src/services/recommendation.js), not an ML model.
 */

// Skills each role typically requires. Keys must match ROLE_SKILLS keys.
export const ROLE_SKILLS = {
  "Data Analyst": [
    "Python",
    "SQL",
    "Excel",
    "Power BI",
    "Statistics",
    "Tableau",
  ],
  "Data Scientist": [
    "Python",
    "SQL",
    "Statistics",
    "Machine Learning",
    "Pandas",
    "Deep Learning",
  ],
  "Software Developer": [
    "Data Structures",
    "Algorithms",
    "Java",
    "Python",
    "Git",
    "SQL",
  ],
  "Full Stack Developer": [
    "HTML/CSS",
    "JavaScript",
    "React",
    "Node.js",
    "MongoDB",
    "Git",
  ],
  "ML Engineer": [
    "Python",
    "Machine Learning",
    "Deep Learning",
    "Pandas",
    "MLOps",
    "SQL",
  ],
};

// Demo student skills. Used as a fallback when the profile has no skills yet.
export const DEMO_STUDENT_SKILLS = [
  "Python",
  "SQL",
  "Excel",
  "Power BI",
  "Data Structures",
  "Git",
];

// Demo companies. Each opens in one of the roles defined above.
export const DEMO_COMPANIES = [
  {
    id: "tcs",
    company: "TCS",
    role: "Data Analyst",
    requiredSkills: ["Python", "SQL", "Excel", "Power BI"],
    minCgpa: 7.0,
    tier: "Tier 1 / 2 / 3",
  },
  {
    id: "infosys",
    company: "Infosys",
    role: "Software Developer",
    requiredSkills: ["Data Structures", "Algorithms", "Java", "SQL"],
    minCgpa: 6.5,
    tier: "Tier 1 / 2 / 3",
  },
  {
    id: "accenture",
    company: "Accenture",
    role: "Full Stack Developer",
    requiredSkills: ["JavaScript", "React", "Node.js", "MongoDB"],
    minCgpa: 7.0,
    tier: "Tier 1 / 2",
  },
  {
    id: "zoho",
    company: "Zoho",
    role: "Software Developer",
    requiredSkills: ["Data Structures", "Java", "Git", "SQL"],
    minCgpa: 6.0,
    tier: "Tier 1 / 2 / 3",
  },
  {
    id: "mu-sigma",
    company: "Mu Sigma",
    role: "Data Analyst",
    requiredSkills: ["Python", "SQL", "Excel", "Statistics"],
    minCgpa: 6.5,
    tier: "Tier 1 / 2 / 3",
  },
  {
    id: "fractal",
    company: "Fractal Analytics",
    role: "Data Scientist",
    requiredSkills: ["Python", "SQL", "Statistics", "Machine Learning"],
    minCgpa: 7.5,
    tier: "Tier 1 / 2",
  },
  {
    id: "wipro",
    company: "Wipro",
    role: "ML Engineer",
    requiredSkills: ["Python", "Machine Learning", "Deep Learning", "SQL"],
    minCgpa: 7.0,
    tier: "Tier 1 / 2 / 3",
  },
  {
    id: "cognizant",
    company: "Cognizant",
    role: "Full Stack Developer",
    requiredSkills: ["HTML/CSS", "JavaScript", "React", "Git"],
    minCgpa: 6.5,
    tier: "Tier 1 / 2 / 3",
  },
];

/**
 * Learning resources for missing skills. Only well-known, reliable platforms
 * with real, stable top-level URLs are used; every link opens in a new tab.
 */
export const LEARNING_RESOURCES = {
  Python: [
    { platform: "Python.org", url: "https://www.python.org/about/gettingstarted/" },
    { platform: "freeCodeCamp", url: "https://www.freecodecamp.org/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=python+full+course" },
  ],
  SQL: [
    { platform: "SQLBolt", url: "https://sqlbolt.com/" },
    { platform: "W3Schools", url: "https://www.w3schools.com/sql/" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=sql+full+course" },
  ],
  Excel: [
    { platform: "Microsoft Learn", url: "https://learn.microsoft.com/en-us/training/browse/?products=m365" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=excel+for+beginners" },
  ],
  "Power BI": [
    { platform: "Microsoft Learn", url: "https://learn.microsoft.com/en-us/training/powerplatform/power-bi" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=power+bi+tutorial" },
  ],
  Statistics: [
    { platform: "Khan Academy", url: "https://www.khanacademy.org/math/statistics-probability" },
    { platform: "Coursera", url: "https://www.coursera.org/browse/data-science" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=statistics+for+data+science" },
  ],
  Tableau: [
    { platform: "Tableau Learning", url: "https://www.tableau.com/learn/training" },
    { platform: "Coursera", url: "https://www.coursera.org/browse/data-science" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=tableau+tutorial" },
  ],
  "Machine Learning": [
    { platform: "Kaggle Learn", url: "https://www.kaggle.com/learn" },
    { platform: "Coursera", url: "https://www.coursera.org/browse/data-science" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=machine+learning+full+course" },
  ],
  "Deep Learning": [
    { platform: "Kaggle Learn", url: "https://www.kaggle.com/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=deep+learning+course" },
  ],
  Pandas: [
    { platform: "Kaggle Learn", url: "https://www.kaggle.com/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=pandas+python+tutorial" },
  ],
  MLOps: [
    { platform: "Kaggle Learn", url: "https://www.kaggle.com/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=mlops+course" },
  ],
  "Data Structures": [
    { platform: "freeCodeCamp", url: "https://www.freecodecamp.org/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=data+structures+full+course" },
  ],
  Algorithms: [
    { platform: "VisuAlgo", url: "https://visualgo.net/" },
    { platform: "freeCodeCamp", url: "https://www.freecodecamp.org/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=algorithms+full+course" },
  ],
  OOP: [
    {
      platform: "Oracle Java Tutorials",
      url: "https://docs.oracle.com/javase/tutorial/java/concepts/",
    },
    {
      platform: "MDN Web Docs",
      url: "https://developer.mozilla.org/en-US/docs/Glossary/OOP",
    },
  ],
  DBMS: [
    { platform: "SQLBolt", url: "https://sqlbolt.com/" },
    { platform: "W3Schools", url: "https://www.w3schools.com/sql/" },
  ],
  "Operating Systems": [
    {
      platform: "Operating Systems: Three Easy Pieces",
      url: "https://pages.cs.wisc.edu/~remzi/OSTEP/",
    },
    {
      platform: "YouTube",
      url: "https://www.youtube.com/results?search_query=operating+systems+full+course",
    },
  ],
  "Computer Networks": [
    { platform: "Cisco Networking Academy", url: "https://www.netacad.com/" },
    {
      platform: "YouTube",
      url: "https://www.youtube.com/results?search_query=computer+networks+full+course",
    },
  ],
  Java: [
    { platform: "W3Schools", url: "https://www.w3schools.com/java/" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=java+full+course" },
  ],
  Git: [
    { platform: "Git Documentation", url: "https://git-scm.com/doc" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=git+and+github+for+beginners" },
  ],
  "HTML/CSS": [
    { platform: "freeCodeCamp", url: "https://www.freecodecamp.org/learn" },
    { platform: "W3Schools", url: "https://www.w3schools.com/html/" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=html+css+full+course" },
  ],
  JavaScript: [
    { platform: "freeCodeCamp", url: "https://www.freecodecamp.org/learn" },
    { platform: "MDN Web Docs", url: "https://developer.mozilla.org/en-US/docs/Web/JavaScript" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=javascript+full+course" },
  ],
  React: [
    { platform: "React Docs", url: "https://react.dev/learn" },
    { platform: "freeCodeCamp", url: "https://www.freecodecamp.org/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=react+js+full+course" },
  ],
  "Node.js": [
    { platform: "Node.js Docs", url: "https://nodejs.org/en/learn" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=nodejs+full+course" },
  ],
  MongoDB: [
    { platform: "MongoDB University", url: "https://learn.mongodb.com/" },
    { platform: "YouTube", url: "https://www.youtube.com/results?search_query=mongodb+full+course" },
  ],
};

/**
 * Common skill-name variations -> the canonical key in LEARNING_RESOURCES.
 * The backend readiness service returns canonical names (OOP, DBMS,
 * Operating Systems, Computer Networks), but aliases are matched too so a
 * differently-spelled skill never falls through to "No learning resources".
 */
const LEARNING_RESOURCE_ALIASES = {
  oop: "OOP",
  "object oriented": "OOP",
  "object oriented programming": "OOP",
  "object-oriented programming": "OOP",
  dbms: "DBMS",
  "database management system": "DBMS",
  "database management systems": "DBMS",
  os: "Operating Systems",
  "operating system": "Operating Systems",
  "operating systems": "Operating Systems",
  cn: "Computer Networks",
  "computer network": "Computer Networks",
  "computer networks": "Computer Networks",
  ds: "Data Structures",
  "data structures": "Data Structures",
  dsa: "Data Structures",
  "data structures and algorithms": "Data Structures",
  algo: "Algorithms",
  algorithms: "Algorithms",
};

/**
 * Learning resources for a backend-reported missing skill.
 *
 * Exact canonical keys win; otherwise a documented alias is resolved.
 * Unknown skills return [] (the card then says so honestly). Duplicate URLs
 * are removed so a card never shows the same link twice.
 */
export function getLearningResources(skill) {
  if (typeof skill !== "string" || skill.trim() === "") return [];

  const name = skill.trim();
  const key =
    LEARNING_RESOURCES[name] !== undefined
      ? name
      : LEARNING_RESOURCE_ALIASES[name.toLowerCase()] ??
        LEARNING_RESOURCE_ALIASES[
          name.toLowerCase().replace(/[^a-z0-9]/g, "")
        ];

  const resources = key ? LEARNING_RESOURCES[key] : null;
  if (!Array.isArray(resources)) return [];

  const seen = new Set();
  return resources.filter((resource) => {
    if (!resource?.url || seen.has(resource.url)) return false;
    seen.add(resource.url);
    return true;
  });
}
