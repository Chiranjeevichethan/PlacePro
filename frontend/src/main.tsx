import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ProfileProvider } from "./context/ProfileContext";
import { ToastProvider } from "./components/ui/Toast";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <ProfileProvider>
          <App />
        </ProfileProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
