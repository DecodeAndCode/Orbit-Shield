import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Ion } from "cesium";
import App from "./App.tsx";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./index.css";

Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30_000,
      staleTime: 10_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
