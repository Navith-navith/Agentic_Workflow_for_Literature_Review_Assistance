/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:  ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono:  ["var(--font-geist-mono)", "monospace"],
        display: ["'DM Serif Display'", "Georgia", "serif"],
      },
      colors: {
        brand: {
          50:  "#f0f9ff",
          100: "#e0f2fe",
          200: "#bae6fd",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          900: "#0c4a6e",
        },
        surface: {
          DEFAULT: "#0f1117",
          card:    "#161b27",
          border:  "#1e2639",
          hover:   "#1a2236",
        },
      },
      animation: {
        "fade-in":    "fadeIn 0.4s ease forwards",
        "slide-up":   "slideUp 0.4s ease forwards",
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "shimmer":    "shimmer 1.5s infinite",
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: "translateY(16px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};
