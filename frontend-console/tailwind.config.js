/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        bg0: '#F4F6FA',
        bg1: '#FFFFFF',
        bg2: '#FFFFFF',
        bg3: '#F1F4F9',
        fg0: '#0F172A',
        fg1: '#475569',
        fg2: '#94A3B8',
        accent: '#4F6BED',
        ok: '#059669',
        run: '#D97706',
        warn: '#EA580C',
        err: '#E11D48',
        info: '#0284C7',
      },
      borderColor: { line: 'rgba(15,23,42,0.08)' },
      fontFamily: {
        sans: ['Inter', '"PingFang SC"', '"Noto Sans SC"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'monospace'],
      },
      borderRadius: { card: '12px', inner: '8px' },
      // 整体字号上调一档：xs 13 / sm 14 / base 15
      fontSize: {
        xs: ['13px', '18px'],
        sm: ['14px', '20px'],
        base: ['15px', '22px'],
        lg: ['17px', '24px'],
        xl: ['20px', '28px'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,23,42,0.04), 0 4px 16px rgba(15,23,42,0.05)',
        lift: '0 2px 4px rgba(15,23,42,0.06), 0 12px 28px rgba(79,107,237,0.10)',
      },
      keyframes: {
        breathe: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.35' } },
        slidein: { from: { opacity: '0', transform: 'translateY(-4px)' }, to: { opacity: '1', transform: 'none' } },
        fadein: { from: { opacity: '0' }, to: { opacity: '1' } },
      },
      animation: {
        breathe: 'breathe 1.6s ease-in-out infinite',
        slidein: 'slidein 160ms ease-out',
        fadein: 'fadein 120ms ease-out',
      },
    },
  },
  plugins: [],
}
