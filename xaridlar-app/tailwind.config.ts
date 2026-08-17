import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dizayn tokenlari — sanoat/gaz mavzusi
        ink: {
          DEFAULT: "#1B2430",
          50: "#f3f5f7",
          100: "#e2e7ec",
          600: "#3a4756",
          700: "#2a3542",
          800: "#212b36",
          900: "#1B2430",
          950: "#121820",
        },
        flame: {
          DEFAULT: "#E8830C",
          50: "#fff6ec",
          100: "#ffe8cc",
          400: "#f59e3d",
          500: "#E8830C",
          600: "#c96c05",
          700: "#a2560a",
        },
        steel: {
          DEFAULT: "#3B6E8F",
          50: "#eef4f8",
          100: "#d6e4ee",
          400: "#5a8dac",
          500: "#3B6E8F",
          600: "#2f586f",
          700: "#274757",
        },
        paper: {
          DEFAULT: "#F7F6F2",
          card: "#ffffff",
          dark: "#ecebe5",
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(27,36,48,0.08), 0 8px 24px rgba(27,36,48,0.06)",
        pop: "0 12px 40px rgba(27,36,48,0.16)",
      },
      borderRadius: {
        xl: "0.9rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
