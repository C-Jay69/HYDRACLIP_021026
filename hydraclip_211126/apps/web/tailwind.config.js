/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx}", "./components/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#05070f",
        panel: "#0a1020",
        panel2: "#101a33",
        line: "#1e2a4a",
        accent: "#35f2c1",
        accent2: "#8b5cf6",
        muted: "#8fa0c4",
      },
      boxShadow: {
        glow: "0 0 60px rgba(53,242,193,0.12)",
      },
      backgroundImage: {
        hero:
          "radial-gradient(circle at 15% 10%, rgba(139,92,246,0.22), transparent 42%), radial-gradient(circle at 85% 0%, rgba(53,242,193,0.15), transparent 38%)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
