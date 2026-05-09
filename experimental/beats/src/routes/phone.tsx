import { PhoneControlPanel } from "@/components/phone-control-panel";
import { createFileRoute } from "@tanstack/react-router";

function PhoneControlPage() {
  return (
    <main className="min-h-svh w-full bg-[#0b0f16]">
      <PhoneControlPanel />
    </main>
  );
}

export const Route = createFileRoute("/phone")({
  component: PhoneControlPage,
});
