import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f5f7fa",
        ink: "#0b1220",
        navy: "#101a2d",
        line: "#e5e9ef"
      },
      fontFamily: { sans: ["var(--font-geist-sans)", "Inter", "sans-serif"], mono: ["var(--font-geist-mono)", "monospace"] }
    }
  },
  plugins: []
};

export default config;
