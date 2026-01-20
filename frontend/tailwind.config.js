/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Existing colors
        primary: '#4F46E5', // Indigo 600
        secondary: '#10B981', // Emerald 500
        dark: '#111827', // Gray 900
        light: '#F3F4F6', // Gray 100
        // Neon accent colors
        'neon-green': '#39FF14',
        'cyan-blue': '#00D4FF',
        // Dark theme background
        'dark-bg': '#0a0a0f',
        // Glass effect colors (with opacity)
        'glass': {
          DEFAULT: 'rgba(255, 255, 255, 0.1)',
          'border': 'rgba(255, 255, 255, 0.2)',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        // Neon glow effects
        'neon-green': '0 0 5px rgba(57, 255, 20, 0.5), 0 0 20px rgba(57, 255, 20, 0.3)',
        'neon-green-lg': '0 0 10px rgba(57, 255, 20, 0.6), 0 0 40px rgba(57, 255, 20, 0.4)',
        'neon-cyan': '0 0 5px rgba(0, 212, 255, 0.5), 0 0 20px rgba(0, 212, 255, 0.3)',
        'neon-cyan-lg': '0 0 10px rgba(0, 212, 255, 0.6), 0 0 40px rgba(0, 212, 255, 0.4)',
        // Glass card shadow
        'glass': '0 8px 32px rgba(0, 0, 0, 0.3)',
      },
      backdropBlur: {
        'glass': '12px',
      }
    },
  },
  plugins: [],
}
