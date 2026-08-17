import { useState } from "react";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Prediction from "./pages/Prediction";
import StudentProfile from "./pages/StudentProfile";
import PerformanceAnalysis from "./pages/PerformanceAnalysis";
import About from "./pages/About";

import { isAuthenticated, logout } from "./services/auth";

import "./App.css";

function App() {
  const [currentPage, setCurrentPage] = useState("dashboard");
  const [authenticated, setAuthenticated] = useState(() => isAuthenticated());
  const [editProfileOpen, setEditProfileOpen] = useState(false);

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
        setCurrentPage={setCurrentPage}
        onEditProfile={handleEditProfile}
        onLogout={handleLogout}
      />

      <div className="app-body">
        {/* Left sidebar */}
        <Sidebar
          currentPage={currentPage}
          setCurrentPage={setCurrentPage}
        />

        {/* Main page content */}
        <main className="main-content">
          {currentPage === "dashboard" && (
            <Dashboard onNavigate={setCurrentPage} />
          )}

          {currentPage === "prediction" && (
            <Prediction />
          )}

          {currentPage === "profile" && (
            <StudentProfile
              editOpen={editProfileOpen}
              onRequestEdit={() => setEditProfileOpen(true)}
              onCloseEdit={() => setEditProfileOpen(false)}
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
