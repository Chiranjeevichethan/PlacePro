import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// PlacePro Phase 18 - Student Dashboard
// The backend URL is configured via VITE_API_URL (see .env.example),
// never hard-coded in components. The dev server proxies nothing -
// the API client talks to the backend directly (CORS is open in dev).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
