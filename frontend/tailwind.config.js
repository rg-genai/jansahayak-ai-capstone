/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        indiaNavy: '#0f2942',
        indiaSaffron: '#e86f1c',
        indiaGreen: '#138808',
      },
    },
  },
  plugins: [],
}
