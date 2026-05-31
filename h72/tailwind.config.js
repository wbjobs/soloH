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
        space: {
          950: '#0A192F',
          900: '#112240',
          800: '#1D3557',
          700: '#2A4568',
        },
        quantum: {
          400: '#64FFDA',
          500: '#4CD7B8',
          600: '#35B096',
        },
        energy: {
          400: '#FF6B35',
          500: '#F75C24',
          600: '#E04E18',
        },
        slate: {
          300: '#CCD6F6',
          400: '#A8B2D1',
          500: '#8892B0',
          600: '#6B7599',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        sans: ['Noto Sans SC', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
        'slide-in': 'slide-in 0.5s ease-out',
        'fade-in': 'fade-in 0.6s ease-out',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(100, 255, 218, 0.3)' },
          '50%': { boxShadow: '0 0 20px rgba(100, 255, 218, 0.6)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'slide-in': {
          '0%': { transform: 'translateX(-20px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
