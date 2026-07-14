/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // ----- Base surfaces (deep space-navy, not pure black) -----
        void: "#0A0E16",
        surface: "#10151F",
        "surface-raised": "#1A2130",
        "surface-hover": "#222B40",
        border: {
          DEFAULT: "#232A3B",
          subtle: "#1A2130",
        },

        // ----- Text -----
        ink: {
          primary: "#E8EAF0",
          secondary: "#8B93A7",
          muted: "#5B6478",
        },

        // ----- Severity semantic ramp (the core visual language) -----
        severity: {
          normal: "#2DD4BF",      // teal -- calm, watching, nothing wrong
          suspicious: "#F0B429",  // amber -- signature accent, "pay attention"
          critical: "#E5484D",    // refined red -- Radix-style, not neon/alarm-red
        },
      },

      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        sans: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },

      keyframes: {
        // Powers the header "Risk Pulse" gauge -- a slow, heartbeat-like
        // breathing motion, not a jarring blink. Speed is controlled
        // per-instance via animation-duration utility overrides.
        pulseRing: {
          "0%, 100%": { transform: "scale(1)", opacity: "0.55" },
          "50%": { transform: "scale(1.15)", opacity: "0.15" },
        },
        // Subtle entrance for new live-feed events, so the feed feels
        // alive without being distracting.
        feedIn: {
          "0%": { opacity: "0", transform: "translateY(-6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-ring": "pulseRing 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "feed-in": "feedIn 0.35s ease-out",
      },

      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};