import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
      "/appointments": {
        target: "http://localhost:8000",
      },
      "/clinic": {
        target: "http://localhost:8000",
      },
      "/health": {
        target: "http://localhost:8000",
      },
      "/api": {
        target: "http://localhost:8000",
      },
    },
  },
});
