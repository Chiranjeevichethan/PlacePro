# PLACEPRO – AI Placement Prediction System

> An AI-based intelligent student placement prediction and recommendation system designed to help students understand their placement readiness and improve their career opportunities.

## 📌 Project Overview

**PlacePro** is an AI-powered student placement prediction platform that analyzes academic performance, technical skills, internships, certifications, projects, aptitude, and other student attributes to estimate placement probability.

The system provides students with:

- 📊 Placement readiness insights
- 🤖 AI/ML-based placement prediction
- 🎯 Personalized recommendations
- 📈 Performance analysis
- 👨‍🎓 Student profile management
- 🔍 Easy navigation and page search
- 🔐 Student authentication interface

This repository contains the **frontend application** of the PlacePro system.

---

## ✨ Features

### 🏠 Dashboard

The dashboard provides a quick overview of the placement system.

- Total students
- Placement rate
- Best-performing ML model
- Model accuracy
- Placement overview
- Placement trend
- Strength areas
- Areas to improve
- AI-powered placement insights

### 🎯 Placement Prediction

Students can enter their academic and professional information to generate a placement prediction.

The prediction interface supports:

- CGPA
- Skills
- Internship information
- Certifications
- Projects
- Aptitude performance
- Other placement-related attributes

The current frontend uses demo/mock prediction logic and is structured to connect with the backend ML API.

### 👨‍🎓 Student Profile

Students can view and edit their profile information.

Profile information includes:

- Name
- Branch
- CGPA
- Attendance
- Certifications
- Internships
- Projects
- GitHub repositories
- LinkedIn connections
- College tier

Profile updates are persisted using browser local storage in the current frontend implementation.

### 📈 Performance Analysis

Provides visual analysis of student performance and placement-related metrics.

### 🔐 Authentication

The frontend currently provides a mock authentication system with:

- Email / Username login
- Password field
- Remember Me
- Password visibility toggle
- Logout
- Google login UI
- GitHub login UI
- LinkedIn login UI

> Social login buttons are currently mock interfaces and can be connected to real OAuth authentication when the backend is implemented.

### 🔎 Page Search

The navigation bar includes a page search feature.

Supported interactions:

- Search pages
- Keyboard navigation
- Arrow-key selection
- Enter to navigate
- Escape to close
- Responsive mobile search

---

## 🛠️ Tech Stack

### Frontend

- React.js
- JavaScript
- HTML5
- CSS3
- Vite

### UI / Visualization

- Responsive CSS
- SVG icons and illustrations
- CSS gradients
- Interactive UI components

### Storage

- Browser Local Storage
- Session Storage

### Backend Integration

The frontend contains an API integration layer designed for connection with the PlacePro backend and machine learning model.

---

## 📁 Project Structure

```text
frontend/
│
├── public/
│   ├── favicon.svg
│   └── icons.svg
│
├── src/
│   │
│   ├── assets/
│   │
│   ├── components/
│   │   ├── EditProfileModal.jsx
│   │   ├── IconMark.jsx
│   │   ├── Logo.jsx
│   │   ├── Navbar.jsx
│   │   ├── ProfileDropdown.jsx
│   │   ├── RecommendationPanel.jsx
│   │   ├── SearchBar.jsx
│   │   ├── Sidebar.jsx
│   │   ├── StatsCard.jsx
│   │   └── StudentForm.jsx
│   │
│   ├── pages/
│   │   ├── About.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Login.jsx
│   │   ├── PerformanceAnalysis.jsx
│   │   ├── Prediction.jsx
│   │   └── StudentProfile.jsx
│   │
│   ├── services/
│   │   ├── api.js
│   │   └── auth.js
│   │
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   └── main.jsx
│
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
└── README.md
