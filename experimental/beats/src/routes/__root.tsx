import BaseLayout from "@/layouts/base-layout";
import { Outlet, createRootRoute } from "@tanstack/react-router";

function Root() {
  return (
    <BaseLayout>
      <Outlet />
    </BaseLayout>
  );
}

export const Route = createRootRoute({
  component: Root,
});
