import { RouterProvider } from "@tanstack/react-router";
import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { syncWithLocalTheme } from "./actions/theme";
import { PeripheralEventsProvider } from "./actions/ws/providers/PeripheralEventsProvider";
import { PeripheralProvider } from "./actions/ws/providers/PeripheralProvider";
import { WSProvider } from "./actions/ws/websocket";
import { router } from "./utils/routes";

export default function App() {
  useEffect(() => {
    syncWithLocalTheme();
  }, []);

  return <RouterProvider router={router} />
}

const root = createRoot(document.getElementById("app")!);
root.render(
  <WSProvider url="ws://localhost:8765">
    <React.StrictMode>
        <PeripheralEventsProvider>
            <PeripheralProvider>
              <App/>
            </PeripheralProvider>
        </PeripheralEventsProvider>
    </React.StrictMode>
  </WSProvider>
  ,
);
