/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#132b35", accent: "#087e68", canvas: "#f5f7f8" },
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
