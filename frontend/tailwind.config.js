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

        // --- Couleurs d'accent par rôle (identité visuelle du tableau de
        // bord et de la barre latérale — voir DashboardLayout.tsx
        // ROLE_THEMES). Même forme que `navy` (deep/DEFAULT/light) pour
        // rester interchangeables partout où `navy` est utilisé aujourd'hui.
        forest: { deep: "#142E22", DEFAULT: "#1F5C3F", light: "#2D7A54" }, // Direction/Fondateur
        plum: { deep: "#2E1F42", DEFAULT: "#4A2F6B", light: "#64408F" },   // Censeur
        rust: { deep: "#4A2A10", DEFAULT: "#B35A1E", light: "#D97A35" },   // Surveillant
        teal: { deep: "#0F3B3D", DEFAULT: "#1B6B6E", light: "#279194" },  // Enseignant
        rose: { deep: "#4A1830", DEFAULT: "#A83A5E", light: "#C95580" },  // Parent
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
