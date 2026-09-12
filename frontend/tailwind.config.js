/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        forest: {
          50: '#F1F7F1',
          100: '#DDEFE5',
          200: '#B8DFC9',
          300: '#8ACAA7',
          400: '#56B083',
          500: '#2FA878',
          600: '#236B4F', // Primary brand
          700: '#1D5A42',
          800: '#174A38', // Primary dark
          900: '#0F3326',
        },
        accent: {
          teal: '#39B982', // Accent fresh green/teal
          mint: '#62C9A0',
          dark: '#2A9567',
          light: '#E6F8F0',
        },
        nature: {
          bg: '#F7FAF7',
          surface: '#FFFFFF',
          soft: '#F1F7F1',
          muted: '#EAF2EA',
          border: '#DCE8DC',
          borderSubtle: '#EBF2EB',
        },
        brand: {
          50: '#F1F7F1',
          100: '#DDEFE5',
          200: '#B8DFC9',
          300: '#8ACAA7',
          400: '#56B083',
          500: '#2FA878',
          600: '#236B4F',
          700: '#1D5A42',
          800: '#174A38',
          900: '#0F3326',
          accent: '#39B982',
        },
        dark: {
          bg: '#0B130E',
          card: '#121D16',
          cardHover: '#1B2C22',
          border: '#22382C',
          text: '#F5FAF6',
          subtext: '#98B3A4',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Outfit', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
