# Frontend — Pages

## frontend/src/main.tsx

**What it does:** React entry point. Mounts `<App />` into `#root` wrapped in `StrictMode`, and imports `index.css` (Tailwind directives).

**External services:** None.

**What calls it:** Loaded by `index.html` as the Vite module entry point.

---

## frontend/src/App.tsx

**What it does:** Top-level React component. Wraps the app in a `BrowserRouter` and declares four routes: `/` → `SearchPage`, `/results` → `ResultsPage`, `/orders` → `OrdersPage`, `/procurement` → `ProcurementBoard`.

**External services:** None.

**What calls it:** `main.tsx`.

---

## frontend/src/pages/SearchPage.tsx

**What it does:** Top-level state owner for the search flow. Manages part results (appended as SSE events arrive), clarify question, detail panel selection, and order confirm modal. Renders `SearchBar`, streams results via `streamSearch` into `PartCard` list, opens `PartDetail` on card click, opens `OrderConfirm` on "Order" click, and navigates to `/orders` after a confirmed order. The `onSearch` callback accepts four parameters — VIN, query, urgency, and `urgency_deadline` — and passes all four through to the navigate state: `{ vin, query, urgency, urgency_deadline }`.

**External services:** Backend `/search` SSE stream (via `streamSearch`), `/orders` POST (via `OrderConfirm`).

**What calls it:** `App.tsx` route `/`. Receives `onSearch` prop from `SearchBar.tsx`.

---

## frontend/src/pages/ResultsPage.tsx

**What it does:** Results screen that fires on mount, streams parts via `streamSearch`, and applies `applyFilters` client-side to the received `SearchResultPart[]` array. Manages all result-flow state: `results`, `isStreaming`, `clarifyQuestion`, `searchError`, `selectedResult`, `confirmTarget`, `filters`, `procureTarget`, `selectedVendorPart`, `procurementJob`, and `procureDeadline`. `LocationState` includes `urgency_deadline: string | null`. Redirects to `/` if accessed without router state. Header includes navigation links for "Orders" and "Procurement".

Procurement flow: `PartDetail` "Procure →" sets `procureTarget` and `procureDeadline` → `VendorSelector` modal opens (fetches vendors for the part), on vendor select calls `createProcurementJob` → `OutreachConfirm` modal opens → user reviews/edits the Haiku-generated email, `sendOutreach` sends it → navigates to `/procurement` and clears all procure state.

**External services:** Backend `/search` SSE stream (via `streamSearch`), `POST /procurement/jobs` (create), `POST /procurement/jobs/{id}/send` (send outreach via `OutreachConfirm`).

**What calls it:** `App.tsx` route `/results`.

---

## frontend/src/pages/OrdersPage.tsx

**What it does:** Fetches all orders on mount via `getOrders()` and renders them in `OrderHistory`. Shows loading shimmer while fetching, error message on failure, and the order table on success. Provides a back-to-search link.

**External services:** Backend `GET /orders`.

**What calls it:** `App.tsx` route `/orders`.

---

## frontend/src/pages/ProcurementBoard.tsx

**What it does:** Full-page job tracking board at `/procurement`. On mount, fetches all procurement jobs via `getProcurementJobs()` and opens a Supabase Realtime channel (`procurement_jobs_realtime`) subscribed to `postgres_changes` on the `procurement_jobs` table. Incoming change events upsert into the local `jobs` state and also patch `selected` if the updated job is currently open. Renders jobs as a table of `ProcurementJobRow` rows; clicking a row opens `VendorOutreachPanel` as a slide-in panel. `handleJobUpdate` propagates panel-driven mutations (send follow-up, accept, reject) back into both `jobs` and `selected`. Shows loading, error, and empty-state slots.

**External services:** Backend `GET /procurement/jobs` (initial load), Supabase Realtime WebSocket (`VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` env vars).

**What calls it:** `App.tsx` route `/procurement`. Navigation link present in `ResultsPage` header and within the board's own header.
