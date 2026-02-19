/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
      },
      colors: {
        // G.Take Theme Colors
        'gt-primary': '#3B82F6',
        'gt-primary-light': '#60A5FA',
        'gt-primary-dark': '#2563EB',
        'gt-secondary': '#8B5CF6',
        'gt-success': '#10B981',
        'gt-warning': '#F59E0B',
        'gt-error': '#EF4444',
        // Backgrounds
        'gt-bg': {
          primary: '#0B1120',
          sidebar: '#0D1321',
          card: 'rgba(30, 41, 59, 0.6)',
          'card-solid': '#151E32',
          elevated: '#1E293B',
          input: '#0F172A',
        },
        // Surfaces
        'gt-surface': {
          1: '#0F172A',
          2: '#1E293B',
          3: '#334155',
          4: '#475569',
        },
        // Text
        'gt-text': {
          primary: '#F8FAFC',
          secondary: '#E2E8F0',
          muted: '#94A3B8',
          subtle: '#64748B',
          disabled: '#475569',
          accent: '#60A5FA',
        },
        // Borders
        'gt-border': {
          subtle: 'rgba(255, 255, 255, 0.05)',
          default: 'rgba(255, 255, 255, 0.1)',
          strong: 'rgba(255, 255, 255, 0.15)',
          accent: 'rgba(59, 130, 246, 0.3)',
        },
      },
      borderRadius: {
        'card': '16px',
        'btn': '12px',
        'container': '24px',
        'gt-sm': '6px',
        'gt-md': '8px',
        'gt-lg': '12px',
        'gt-xl': '16px',
        'gt-2xl': '20px',
      },
      backdropBlur: {
        'gt-sm': '8px',
        'gt-md': '12px',
        'gt-lg': '16px',
        'gt-xl': '24px',
      },
      boxShadow: {
        'gt-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
        'gt-md': '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
        'gt-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.2)',
        'gt-glow': '0 0 20px rgba(59, 130, 246, 0.15)',
        'gt-glow-strong': '0 0 30px rgba(59, 130, 246, 0.25)',
        'gt-inner': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
      },
      animation: {
        'fade-in': 'fadeIn 0.25s ease-out',
        'gt-pulse': 'gtPulse 2s ease-in-out infinite',
        'gt-shimmer': 'gtShimmer 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        gtPulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        gtShimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      backgroundImage: {
        'gt-gradient': 'linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%)',
        'gt-gradient-header': 'linear-gradient(180deg, rgba(59, 130, 246, 0.08) 0%, transparent 60%)',
        'gt-gradient-card': 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, transparent 50%)',
      },
    },
  },
  plugins: [],
}
