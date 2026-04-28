# Frontend — Setup

## frontend/package.json

**What it does:** Defines the frontend npm project. Dependencies: `react@18`, `react-dom@18`, `react-router-dom@6`, `@supabase/supabase-js@^2.0.0` (Supabase Realtime subscription on the procurement job board). Dev dependencies: TypeScript, Vite, `@vitejs/plugin-react`, Tailwind CSS, PostCSS, autoprefixer, and React type definitions. Scripts: `dev`, `build`, `preview`.

**External services:** npm registry at install time; Supabase WebSocket at runtime (via `ProcurementBoard`).

**What calls it:** `npm install` (install deps), `npm run dev` (start Vite dev server), Railway Dockerfile build.

---

## frontend/tsconfig.json

**What it does:** TypeScript compiler config for the frontend. Targets ES2020 with `react-jsx` transform, `bundler` module resolution (Vite), strict mode on. `noEmit: true` because Vite handles transpilation; tsc is only used for type-checking.

**External services:** None.

**What calls it:** `npm run build` runs `tsc && vite build`; IDEs use it for type-checking.

---

## frontend/vite.config.ts

**What it does:** Vite bundler config. Registers `@vitejs/plugin-react` (JSX transform + Fast Refresh). No custom aliases or proxy — the API base URL is configured via `VITE_API_BASE_URL` env var read at runtime in `api/client.ts`.

**External services:** None.

**What calls it:** `vite` CLI (dev server and build).

---

## frontend/tailwind.config.ts

**What it does:** Tailwind CSS config. Content paths cover `index.html` and all `src/**/*.{ts,tsx}` files. Extends the theme with a `fade-in` keyframe animation used by `PartCard` to animate streaming part arrivals.

**External services:** None.

**What calls it:** PostCSS processes `src/index.css` through Tailwind at build/dev time.

---

## frontend/postcss.config.js + frontend/src/index.css

**What they do:** `postcss.config.js` chains Tailwind CSS and Autoprefixer PostCSS plugins. `index.css` declares the three Tailwind directives (`@tailwind base/components/utilities`) that PostCSS expands into the full utility stylesheet.

**External services:** None.

**What calls it:** Vite imports `index.css` via `main.tsx`; PostCSS processes it through Tailwind.
