import { routeTree } from "@/routeTree.gen";
import {
  createBrowserHistory,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router";

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

  return createBrowserHistory();
}

export const router = createRouter({
  defaultPendingMinMs: 0,
  routeTree,
  history: buildRouterHistory(),
});
