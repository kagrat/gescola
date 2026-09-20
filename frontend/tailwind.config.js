/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Palette alignée sur la maquette de référence (gescola-maquette.html)
        navy: {
          DEFAULT: "#1F3358", // ink-900
          deep: "#182A4A",    // ink-950 (sidebar, hero cards)
          light: "#2A4270",   // ink-800
        },
        paper: "#F8F5EE",   // cream-50
        cream: {
          100: "#F0EBDD",
        },
        sky: {
          DEFAULT: "#3E8FD9",
          200: "#BFDCF5",
        },
        ochre: {              // conservé comme alias pour compatibilité, mappé sur ambre de la maquette
          DEFAULT: "#D9822B",
          dark: "#9A5F17",
        },
        pass: "#2FA671",     // emerald-500 (succès / payé / présent)
        brick: "#E1584F",    // coral-500 (alerte / impayé / absent)
        ink: "#1C2333",
        line: "rgba(28,35,51,0.10)",
      },
      fontFamily: {
        display: ["Lora", "ui-serif", "Georgia", "serif"],
        body: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "9px",
        lg: "14px",
      },
    },
  },
  plugins: [],
};
