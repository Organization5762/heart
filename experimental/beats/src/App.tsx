import { RouterProvider } from "@tanstack/react-router";
import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { syncWithLocalTheme } from "./actions/theme";
import { WSProvider } from "./components/websocket";
import { router } from "./utils/routes";

export default function App() {
  useEffect(() => {
    syncWithLocalTheme();
  }, []);

  return <WSProvider url="ws://localhost:8765">
      <RouterProvider router={router} />;
  </WSProvider>
 
}

const root = createRoot(document.getElementById("app")!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
