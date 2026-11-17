/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#006EB9',
          light: '#4C9BE0',
          dark: '#00558F',
        },
        'primary-btn': {
          DEFAULT: '#113EAC',
          hover: '#0E338E',
          active: '#0B2973',
        },
        surface: {
          DEFAULT: '#EAEDFF',
          hover: '#DFE4FD',
        },
        page: '#FAF8FF',
        ink: {
          DEFAULT: '#1D1A2B',
          light: '#373449',
        },
        muted: '#656673',
        'subtle-border': '#E4E6F0',
      },
      fontFamily: {
        fredoka: ['Fredoka', 'sans-serif'],
        sans: ['Geist', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        card: '0 2px 8px -2px rgba(29, 26, 43, 0.05), 0 4px 16px -4px rgba(29, 26, 43, 0.04)',
        sidebar: '1px 0 0 0 rgba(29, 26, 43, 0.06)',
      },
    },
  },
  plugins: [],
}
