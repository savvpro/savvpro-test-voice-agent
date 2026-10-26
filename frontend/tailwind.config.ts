import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // One neutral scale for the whole product: gray and white.
        ink: {
          50: "#F7F7F8",
          100: "#EFEFF1",
          200: "#E2E2E6",
          300: "#C9C9CF",
          400: "#9B9BA3",
          500: "#71717A",
          600: "#52525B",
          700: "#3F3F46",
          800: "#27272A",
          900: "#18181B",
          950: "#0E0E10",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(24,24,27,0.04), 0 10px 30px rgba(24,24,27,0.06)",
        lift: "0 1px 0 rgba(255,255,255,0.6) inset, 0 24px 60px -18px rgba(24,24,27,0.35)",
      },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(14px)" }, to: { opacity: "1", transform: "none" } },
        wave: { "0%,100%": { transform: "scaleY(0.35)" }, "50%": { transform: "scaleY(1)" } },
        ring: { "0%": { transform: "scale(1)", opacity: "0.45" }, "100%": { transform: "scale(1.9)", opacity: "0" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        nudge: { "0%,100%": { transform: "translateY(0)", opacity: "1" }, "50%": { transform: "translateY(-4px)", opacity: "0.55" } },
      },
      animation: {
        "fade-up": "fade-up .6s cubic-bezier(.22,1,.36,1) both",
        wave: "wave 1s ease-in-out infinite",
        ring: "ring 1.6s cubic-bezier(.22,1,.36,1) infinite",
        float: "float 6s ease-in-out infinite",
        nudge: "nudge 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
