import type { Meta, StoryObj } from "@storybook/react-vite";

import { StreamCube } from "./stream-cube";

const SAMPLE_IMAGE =
  "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80";

const meta = {
  title: "Visuals/StreamCube",
  component: StreamCube,
  args: {
    imgURL: SAMPLE_IMAGE,
  },
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "Three.js status display used on the stream route to preview a live or fallback frame.",
      },
    },
  },
  render: (args) => (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-8">
      <div className="h-[520px] w-full max-w-5xl rounded-3xl border border-sky-500/20 bg-slate-950/80 shadow-2xl shadow-sky-950/30">
        <StreamCube {...args} />
      </div>
    </div>
  ),
} satisfies Meta<typeof StreamCube>;

export default meta;

type Story = StoryObj<typeof meta>;

export const WithFrame: Story = {};

export const EmptyState: Story = {
  args: {
    imgURL: null,
  },
};
