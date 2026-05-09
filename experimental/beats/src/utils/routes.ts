import { routeTree } from "@/routeTree.gen";
import {
  createBrowserHistory,
  createHashHistory,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router";
import { isElectronRuntime } from "@/utils/runtime";

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

function buildRouterHistory() {
  if (typeof window === "undefined") {
    return createMemoryHistory({
      initialEntries: ["/"],
    });
  }

  if (!isElectronRuntime()) {
    return createBrowserHistory();
  }

  return createHashHistory();
}

export const router = createRouter({
  defaultPendingMinMs: 0,
  routeTree,
  history: buildRouterHistory(),
});
