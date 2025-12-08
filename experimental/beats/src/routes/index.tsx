import { createFileRoute } from "@tanstack/react-router";

/*
 * Update this page to modify your home page.
 * You can delete this file component to start from a blank page.
 */

function HomePage() {
  return (
    <>
      <div/>
    </>
  );
}

export const Route = createFileRoute("/")({
  component: HomePage,
});
