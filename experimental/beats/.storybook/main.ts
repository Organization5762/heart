import type { StorybookConfig } from "@storybook/react-vite";
import { mergeConfig } from "vite";

import rendererConfig from "../vite.renderer.config.mts";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx|mdx)"],
  addons: ["@storybook/addon-a11y", "@storybook/addon-docs"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  async viteFinal(config) {
    return mergeConfig(config, rendererConfig);
  },
};

export default config;
