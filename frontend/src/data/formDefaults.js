/**
 * Initial (empty) student-form values for the placement prediction form.
 *
 * Lives in its own data module (shared constant, no component) so both
 * the StudentForm component and App.jsx's persistent draft state can
 * import it without breaking React fast refresh.
 */
export const initialFormData = {
  branch: "",
  collegeTier: "",
  cgpa: "",
  backlogs: "",
  codingSkill: "",
  dsaScore: "",
  aptitudeScore: "",
  communicationSkill: "",
  mlKnowledge: "",
  systemDesign: "",
  internships: "",
  projects: "",
  certifications: "",
  hackathons: "",
  openSourceContributions: "",
  extracurricular: "",
};
