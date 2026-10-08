import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f1420",
        panel: "#161c2c",
        border: "#232b3d",
        accent: "#3b82f6",
      },
    },
  },
  plugins: [],
};

export default config;
