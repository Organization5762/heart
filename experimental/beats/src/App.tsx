import { RouterProvider } from "@tanstack/react-router";
import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { syncWithLocalTheme } from "./actions/theme";
import { ImageProvider } from "./actions/ws/providers/ImageProvider";
import { PeripheralEventsProvider } from "./actions/ws/providers/PeripheralEventsProvider";
import { PeripheralProvider } from "./actions/ws/providers/PeripheralProvider";
import { WSProvider } from "./actions/ws/websocket";
import { getConfiguredBeatsWebSocketUrl } from "./config/websocket";
import { router } from "./utils/routes";

const websocketUrl = getConfiguredBeatsWebSocketUrl();

export default function App() {
  useEffect(() => {
    syncWithLocalTheme();
  }, []);

  return <RouterProvider router={router} />;
}

const root = createRoot(document.getElementById("app")!);
root.render(
  <WSProvider url={websocketUrl}>
    <React.StrictMode>
      <PeripheralEventsProvider>
        <PeripheralProvider>
          <ImageProvider>
            <App />
          </ImageProvider>
        </PeripheralProvider>
      </PeripheralEventsProvider>
    </React.StrictMode>
  </WSProvider>,
);
