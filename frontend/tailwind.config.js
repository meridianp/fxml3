/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // Trading platform color scheme
      colors: {
        // Brand colors
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',  // Primary brand color
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },

        // Trading specific colors
        trading: {
          profit: '#10b981',    // Green for profits
          loss: '#ef4444',      // Red for losses
          neutral: '#6b7280',   // Gray for neutral
          buy: '#059669',       // Buy orders
          sell: '#dc2626',      // Sell orders
          pending: '#f59e0b',   // Pending orders
        },

        // Status colors
        status: {
          online: '#10b981',
          offline: '#ef4444',
          warning: '#f59e0b',
          info: '#3b82f6',
        },

        // Dark mode optimized colors
        dark: {
          bg: {
            primary: '#0f172a',    // Main background
            secondary: '#1e293b',  // Card backgrounds
            tertiary: '#334155',   // Elevated surfaces
          },
          text: {
            primary: '#f8fafc',    // Primary text
            secondary: '#cbd5e1',  // Secondary text
            tertiary: '#94a3b8',   // Tertiary text
          },
          border: '#374151',       // Borders
        },
      },

      // Typography for trading interface
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },

      // Spacing for dense trading interfaces
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '100': '25rem',
        '112': '28rem',
        '128': '32rem',
      },

      // Animation for real-time updates
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-green': 'pulseGreen 1s ease-in-out',
        'pulse-red': 'pulseRed 1s ease-in-out',
        'bounce-subtle': 'bounceSubtle 0.5s ease-in-out',
      },

      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseGreen: {
          '0%, 100%': { backgroundColor: '#10b981' },
          '50%': { backgroundColor: '#34d399' },
        },
        pulseRed: {
          '0%, 100%': { backgroundColor: '#ef4444' },
          '50%': { backgroundColor: '#f87171' },
        },
        bounceSubtle: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.02)' },
        },
      },

      // Box shadows for depth
      boxShadow: {
        'trading': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'trading-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },

      // Grid template columns for trading layouts
      gridTemplateColumns: {
        'trading-dashboard': '280px 1fr 320px',
        'trading-data': 'repeat(auto-fit, minmax(300px, 1fr))',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),

    // Custom plugin for trading-specific utilities
    function({ addUtilities }) {
      const newUtilities = {
        '.text-profit': {
          color: '#10b981',
          fontWeight: '600',
        },
        '.text-loss': {
          color: '#ef4444',
          fontWeight: '600',
        },
        '.bg-profit-subtle': {
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
        },
        '.bg-loss-subtle': {
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
        },
        '.trading-card': {
          backgroundColor: '#ffffff',
          borderRadius: '0.5rem',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          border: '1px solid #e5e7eb',
        },
        '.trading-card-dark': {
          backgroundColor: '#1e293b',
          borderRadius: '0.5rem',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.2)',
          border: '1px solid #374151',
        },
      };
      addUtilities(newUtilities);
    },
  ],
};
