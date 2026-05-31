/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    container: {
      center: true,
    },
    extend: {
      colors: {
        tanmu: '#4A2C1A',
        xuanzhi: '#F5F0E6',
        zhusha: '#C0392B',
        'tanmu-light': '#6B4423',
        'tanmu-dark': '#2D1A0F',
        'xuanzhi-dark': '#E8E0D0',
        'zhusha-light': '#E74C3C',
      },
      fontFamily: {
        kai: ['KaiTi', 'STKaiti', 'serif'],
        song: ['SimSun', 'STSong', 'serif'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-zhusha': 'zhusha-pulse 1.5s ease-in-out infinite',
      },
      keyframes: {
        'zhusha-pulse': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(192, 57, 43, 0.7)' },
          '50%': { boxShadow: '0 0 0 12px rgba(192, 57, 43, 0)' },
        },
      },
    },
  },
  plugins: [],
};
