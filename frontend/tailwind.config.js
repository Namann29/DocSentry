/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
const sev = (name) => ({ 50: v("surface2"), 100: v("surface2"), 200: v(name), 300: v(name), 400: v(name), 500: v(name), 600: v(name), 700: v(name), 800: v(name), 900: v(name), 950: v(name) });
const ink = { 50: v("surface2"), 100: v("surface2"), 200: v("fg2"), 300: v("muted"), 400: v("accent"), 500: v("accent"), 600: v("line"), 700: v("surface2"), 800: v("surface"), 900: v("fg"), 950: v("bg") };
const greys = { 50: v("surface2"), 100: v("surface2"), 200: v("line"), 300: v("line"), 400: v("muted"), 500: v("muted"), 600: v("fg2"), 700: v("fg2"), 800: v("surface2"), 900: v("fg"), 950: v("bg") };
const accent = { DEFAULT: v("accent"), 50: v("surface2"), 100: v("surface2"), 200: v("accent"), 300: v("accent"), 400: v("accent"), 500: v("accent"), 600: v("accent"), 700: v("accent"), 800: v("accent"), 900: v("accent") };
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink, navy: ink, accent, slate: greys, stone: greys,
        amber: sev("sev-warn"), orange: sev("sev-warn"), yellow: sev("sev-warn"), red: sev("sev-high"), emerald: sev("sev-ok"),
        white: v("surface"), fog: v("bg"), ivory: v("bg"), paper: v("surface"),
        fg: v("fg"), fg2: v("fg2"), muted: v("muted"), line: v("line"), surface: v("surface"), surface2: v("surface2"), side: v("sidebar"), onaccent: v("on-accent"),
      },
      fontFamily: { display: ['"Source Sans 3"', '"Segoe UI"', 'system-ui', 'sans-serif'], sans: ['"Source Sans 3"', '"Segoe UI"', 'system-ui', 'sans-serif'], mono: ['"IBM Plex Mono"', 'ui-monospace', 'Consolas', 'monospace'] },
      fontWeight: { 700: "600", 800: "600" },
      boxShadow: { soft: "none", page: "0 1px 0 rgba(0,0,0,.4), 0 24px 48px -24px rgba(0,0,0,.8)" },
      keyframes: {
        fade: { from: { opacity: "0" }, to: { opacity: "1" } },
        rise: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        pulseDot: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".35" } },
        scanline: { "0%": { top: "6%" }, "50%": { top: "92%" }, "100%": { top: "6%" } },
        pop: { from: { opacity: "0" }, to: { opacity: "1" } },
      },
      animation: { fade: "fade 180ms ease-out both", rise: "rise 220ms ease-out both", pulseDot: "pulseDot 1.2s ease-in-out infinite", scanline: "scanline 2.2s ease-in-out infinite", pop: "pop 160ms ease-out both" },
    },
  },
  plugins: [],
};