import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteStaticCopy } from "vite-plugin-static-copy";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    viteStaticCopy({
      targets: [
        { src: "node_modules/cesium/Build/Cesium/Workers/**", dest: "cesium/Workers" },
        { src: "node_modules/cesium/Build/Cesium/ThirdParty/**", dest: "cesium/ThirdParty" },
        { src: "node_modules/cesium/Build/Cesium/Assets/**", dest: "cesium/Assets" },
        { src: "node_modules/cesium/Build/Cesium/Widgets/**", dest: "cesium/Widgets" },
      ],
    }),
  ],
  define: {
    CESIUM_BASE_URL: JSON.stringify("/cesium"),
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
