import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      // The full MVP backend owns this API. Port 8000 may be occupied by the
      // legacy OAuth shell, so local development uses the isolated backend.
      "/api": process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001",
    },
  },
});
