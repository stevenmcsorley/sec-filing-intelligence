/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.tsx',
    './app/**/*.ts',
    './components/**/*.tsx',
    './components/**/*.ts',
    './services/**/*.ts',
    './types/**/*.ts',
    './lib/**/*.ts',
  ],
  theme: {
    extend: {
      colors: {
        // Professional dark financial theme colors
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Custom financial theme colors
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
        // Dark theme specific colors
        dark: {
          50: "hsl(220, 13%, 95%)",
          100: "hsl(220, 13%, 90%)",
          200: "hsl(220, 13%, 80%)",
          300: "hsl(220, 13%, 70%)",
          400: "hsl(220, 13%, 60%)",
          500: "hsl(220, 13%, 50%)",
          600: "hsl(220, 13%, 40%)",
          700: "hsl(220, 13%, 30%)",
          800: "hsl(220, 13%, 20%)",
          900: "hsl(220, 13%, 10%)",
          950: "hsl(220, 13%, 5%)",
        },
        // Financial accent colors
        bullish: {
          DEFAULT: "hsl(142, 76%, 36%)", // Green for positive/up
          foreground: "hsl(0, 0%, 100%)",
        },
        bearish: {
          DEFAULT: "hsl(0, 84%, 60%)", // Red for negative/down
          foreground: "hsl(0, 0%, 100%)",
        },
        neutral: {
          DEFAULT: "hsl(220, 13%, 50%)", // Neutral gray
          foreground: "hsl(0, 0%, 100%)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}