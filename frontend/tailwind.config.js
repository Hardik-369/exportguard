/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Neobrutalist palette — bold, high contrast
        'nb-black': '#1a1a1a',
        'nb-white': '#f8f8f8',
        'nb-red': '#e63946',
        'nb-amber': '#f4a261',
        'nb-green': '#2a9d8f',
        'nb-blue': '#264653',
        'nb-border': '#1a1a1a',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'nb': '4px 4px 0px 0px #1a1a1a',
        'nb-sm': '2px 2px 0px 0px #1a1a1a',
        'nb-lg': '6px 6px 0px 0px #1a1a1a',
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [],
}
