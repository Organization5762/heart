import type { Decorator, Preview } from "@storybook/react-vite";
import type { ReactNode } from "react";
import { useEffect } from "react";

import "../src/styles/global.css";

type ThemeMode = "light" | "dark";

type ThemeFrameProps = {
  children: ReactNode;
  theme: ThemeMode;
};

function ThemeFrame({ children, theme }: ThemeFrameProps) {
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.body.classList.toggle("dark", theme === "dark");

    return () => {
      document.documentElement.classList.remove("dark");
      document.body.classList.remove("dark");
    };
  }, [theme]);

  return (
    <div className="bg-background text-foreground min-h-screen p-6">
      {children}
    </div>
  );
}

const themeDecorator: Decorator = (Story, context) => (
  <ThemeFrame theme={context.globals.theme as ThemeMode}>
    <Story />
  </ThemeFrame>
);

const preview: Preview = {
  decorators: [themeDecorator],
  globals: {
    theme: "light" satisfies ThemeMode,
  },
  globalTypes: {
    theme: {
      description: "Global theme for component previews",
      toolbar: {
        title: "Theme",
        icon: "mirror",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
        ],
      },
    },
  },
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    layout: "centered",
  },
};

export default preview;
