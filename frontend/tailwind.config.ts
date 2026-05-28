import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        mk: {
          orange: '#F97316',
          dark: '#0A0A0A',
          card: '#141414',
          border: '#262626',
        },
        success: { DEFAULT: '#22C55E', light: '#BBF7D0' },
        warning: { DEFAULT: '#EAB308', light: '#FEF9C3' },
        error: { DEFAULT: '#EF4444', light: '#FECACA' },
        info: { DEFAULT: '#3B82F6', light: '#BFDBFE' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        h1: ['2rem', { lineHeight: '2.5rem', fontWeight: '700' }],
        h2: ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],
        h3: ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        h4: ['1rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        body: ['0.875rem', { lineHeight: '1.25rem' }],
        caption: ['0.75rem', { lineHeight: '1rem' }],
        label: ['0.75rem', { lineHeight: '1rem', fontWeight: '500' }],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};

export default config;
