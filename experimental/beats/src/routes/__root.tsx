import BaseLayout from "@/layouts/base-layout";
import {
  Outlet,
  createRootRoute,
  useRouterState,
} from "@tanstack/react-router";

function Root() {
  const { hash, pathname } = useRouterState({
    select: (state) => state.location,
  });
  const isPhoneRoute =
    pathname === "/phone" ||
    pathname === "/phone-control" ||
    hash === "#/phone" ||
    hash === "#/phone-control";

  if (isPhoneRoute) {
    return <Outlet />;
  }

  return (
    <BaseLayout>
      <Outlet />
    </BaseLayout>
  );
}

export const Route = createRootRoute({
  component: Root,
});
