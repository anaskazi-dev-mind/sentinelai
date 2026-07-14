import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxies /api/* to the FastAPI backend during development so the
    // frontend can call relative paths (e.g. fetch("/api/v1/events"))
    // without hardcoding http://localhost:8000 everywhere or fighting
    // CORS in dev. Production builds instead read VITE_API_BASE_URL
    // (see src/api.js) and talk to the deployed backend directly.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});