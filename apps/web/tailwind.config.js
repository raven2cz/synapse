/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        'obsidian': '#0a0a0f',
        'slate-deep': '#12121a',
        'slate-darker': '#0f0f17',
        'slate-dark': '#16161f',
        'slate-mid': '#1a1a2e',
        'slate-light': '#2a2a42',
        'slate-base': '#13131b',
        
        // Accents
        'synapse': '#6366f1',
        'pulse': '#8b5cf6',
        'neural': '#06b6d4',
        
        // Text
        'text-primary': '#f8fafc',
        'text-secondary': '#94a3b8',
        'text-muted': '#64748b',
        
        // States
        'success': '#22c55e',
        'warning': '#f59e0b',
        'error': '#ef4444',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'breathe': 'breathe 3s ease-in-out infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': {
            boxShadow: '0 0 8px rgba(34, 197, 94, 0.5)',
            opacity: '1'
          },
          '50%': {
            boxShadow: '0 0 12px rgba(34, 197, 94, 0.8)',
            opacity: '0.8'
          },
        },
        breathe: {
          '0%, 100%': {
            opacity: '0.6',
            transform: 'scale(1)'
          },
          '50%': {
            opacity: '0.95',
            transform: 'scale(1.05)'
          },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
