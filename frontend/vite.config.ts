import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  plugins: [react(), tailwindcss(), cesium()],
  build: {
    chunkSizeWarningLimit: 6000,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          query: ["@tanstack/react-query", "zustand"],
          charts: ["recharts"],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
