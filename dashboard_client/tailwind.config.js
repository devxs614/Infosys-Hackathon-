/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#09090b',
        violet: '#8b5cf6',
        cyan: '#06b6d4',
      },
      boxShadow: {
        glow: '0 0 48px rgba(139, 92, 246, .20)',
        cyan: '0 0 42px rgba(6, 182, 212, .18)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
