import type { Config } from "tailwindcss";
import uiPreset from "../../packages/ui/src/tailwind.preset";

const config: Config = {
  presets: [uiPreset],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  plugins: []
};

export default config;
