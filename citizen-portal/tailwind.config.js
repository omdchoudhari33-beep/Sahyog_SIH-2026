/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Government-portal palette. "gov-blue" is the primary brand/header
        // color, "gov-orange" is the accent used sparingly (borders, CTAs,
        // badges) - not a gradient system, just a couple of flat tones per
        // shade so it reads as an official site, not a startup landing page.
        "gov-blue": {
          DEFAULT: "#0b3d66",
          50: "#eef4f9",
          100: "#d6e6f0",
          200: "#adccdf",
          300: "#7fadc9",
          400: "#4c86a8",
          500: "#2c6690",
          600: "#1c4e75",
          700: "#0b3d66",
          800: "#092f4f",
          900: "#07233b",
        },
        "gov-orange": {
          DEFAULT: "#d9631e",
          50: "#fdf2ea",
          100: "#fbe0cb",
          200: "#f5bd94",
          300: "#ee9a5e",
          400: "#e57c37",
          500: "#d9631e",
          600: "#b64f17",
          700: "#8f3d13",
          800: "#6b2e0f",
          900: "#4a1f0a",
        },
      },
      fontFamily: {
        // Serif for headings (official/formal feel), plain sans for body
        // copy and form controls (readability at small sizes). Loaded via
        // next/font/google in app/layout.js as CSS variables - Hindi text
        // falls through to the system sans-serif stack, which is fine
        // (Devanagari webfont pairing is unnecessary polish for this build).
        serif: ["var(--font-noto-serif)", "Georgia", "'Times New Roman'", "serif"],
        sans: ["var(--font-noto-sans)", "-apple-system", "'Segoe UI'", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
