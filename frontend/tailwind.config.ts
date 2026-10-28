import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        shell: "#11100f",
        rail: "#181716",
        panel: "#201f1d",
        panel2: "#282724",
        line: "#3a3834",
        agent: "#2dd4bf",
        honey: "#f6c453",
        iris: "#a78bfa",
        tomato: "#f87171",
        mint: "#7fdc8c",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(45, 212, 191, 0.24), 0 18px 60px rgba(0, 0, 0, 0.38)",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Consolas", "monospace"],
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
