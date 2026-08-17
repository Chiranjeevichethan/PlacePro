import { Navigate, Route, Routes } from "react-router-dom";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { AssessmentPage } from "./pages/AssessmentPage";
import { CompaniesPage } from "./pages/CompaniesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ImprovementPlanPage } from "./pages/ImprovementPlanPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PredictionPage } from "./pages/PredictionPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ReadinessPage } from "./pages/ReadinessPage";
import { RecommendationsPage } from "./pages/RecommendationsPage";
import { ResumePage } from "./pages/ResumePage";
import { SkillsPage } from "./pages/SkillsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/resume" element={<ResumePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/prediction" element={<PredictionPage />} />
        <Route path="/readiness" element={<ReadinessPage />} />
        <Route path="/assessment" element={<AssessmentPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/companies" element={<CompaniesPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/improvement-plan" element={<ImprovementPlanPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
