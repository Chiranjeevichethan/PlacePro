import { useState } from "react";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Prediction from "./pages/Prediction";
import SalaryPrediction from "./pages/SalaryPrediction";
import CompanyRecommendations from "./pages/CompanyRecommendations";
import SkillGapAnalysis from "./pages/SkillGapAnalysis";
import MockTests from "./pages/MockTests";
import StudentProfile from "./pages/StudentProfile";
import PerformanceAnalysis from "./pages/PerformanceAnalysis";
import About from "./pages/About";

import { isAuthenticated, logout } from "./services/auth";

import "./App.css";

function App() {
  const [currentPage, setCurrentPage] = useState("dashboard");
  const [authenticated, setAuthenticated] = useState(() => isAuthenticated());
  const [editProfileOpen, setEditProfileOpen] = useState(false);
  const [resumeProfileOpen, setResumeProfileOpen] = useState(false);

  if (!authenticated) {
    return (
      <Login
        onLogin={() => {
          setCurrentPage("dashboard");
          setAuthenticated(true);
        }}
      />
    );
  }

  /* Sidebar navigation: leave the profile page -> close both modals so a
     stale open state can't re-open them when the page is revisited. */
  const handleNavigate = (page) => {
    if (page !== "profile") {
      setEditProfileOpen(false);
      setResumeProfileOpen(false);
    }
    setCurrentPage(page);
  };

  const handleEditProfile = () => {
    setCurrentPage("profile");
    setEditProfileOpen(true);
  };

  const handleLogout = () => {
    logout();
    setAuthenticated(false);
  };

  return (
    <div className="app">
      {/* Top navigation */}
      <Navbar
        setCurrentPage={handleNavigate}
        onEditProfile={handleEditProfile}
        onLogout={handleLogout}
      />

      <div className="app-body">
        {/* Left sidebar */}
        <Sidebar
          currentPage={currentPage}
          setCurrentPage={handleNavigate}
        />

        {/* Main page content */}
        <main className="main-content">
          {currentPage === "dashboard" && (
            <Dashboard onNavigate={setCurrentPage} />
          )}

          {currentPage === "prediction" && (
            <Prediction />
          )}

          {currentPage === "salary" && (
            <SalaryPrediction />
          )}

          {currentPage === "companies" && (
            <CompanyRecommendations />
          )}

          {currentPage === "skillgap" && (
            <SkillGapAnalysis />
          )}

          {currentPage === "mocktests" && (
            <MockTests />
          )}

          {currentPage === "profile" && (
            <StudentProfile
              editOpen={editProfileOpen}
              onRequestEdit={() => setEditProfileOpen(true)}
              onCloseEdit={() => setEditProfileOpen(false)}
              resumeOpen={resumeProfileOpen}
              onRequestResume={() => setResumeProfileOpen(true)}
              onCloseResume={() => setResumeProfileOpen(false)}
            />
          )}

          {currentPage === "performance" && (
            <PerformanceAnalysis />
          )}

          {currentPage === "about" && (
            <About />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
