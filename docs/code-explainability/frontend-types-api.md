# Frontend — Types & API

## frontend/src/types/index.ts

**What it does:** TypeScript type definitions mirroring all backend Pydantic schemas. Core types: `Part`, `FitmentResult`, `FitmentConfidence`, `SearchResultPart`, `VINSpec`, `Order`, `OrderCreate`. Vendor outreach types: `Vendor`, `VendorPart`, `JobStatus` union (includes the terminal `'failed'` state), `ProcurementEvent`, `ProcurementJob` (full job snapshot including all email fields, parsed fields, ranking score, `attempt_count`, and nested vendor + events), `ProcurementJobCreate` (POST body). Single source of truth for all data shapes used across API clients and components.

**External services:** None.

**What calls it:** All `src/api/` modules and all components import types from here.

---

## frontend/src/api/client.ts

**What it does:** Base fetch wrapper. Reads `VITE_API_BASE_URL` from Vite env (defaults to `http://localhost:8000`). Exports `apiGet<T>` and `apiPost<T>` helpers that parse JSON and throw on non-2xx. Also re-exports `API_BASE` for use by `search.ts` which needs direct `fetch` access for SSE streaming.

**External services:** Backend FastAPI server.

**What calls it:** `api/search.ts`, `api/orders.ts`, `api/vin.ts`, `api/vendors.ts`, `api/procurement.ts`.

---

## frontend/src/api/search.ts

**What it does:** Implements SSE streaming for the `/search` endpoint. `streamSearch()` opens a `fetch` + `ReadableStream` connection, parses `data:` lines from the stream, and dispatches to typed callbacks: `onPart` (each result card), `onClarify` (ambiguous query question), `onDone`, `onError`. The request carries an optional `urgency_deadline`. `done` and `clarify` count as clean termination — the "Connection lost" error fires only when the stream closes without a terminal event (network drop or server crash). A 60-second inactivity watchdog aborts a stalled stream and reports a timeout, while caller-initiated aborts stay silent. Returns an `AbortController` so callers can cancel on component unmount.

**External services:** Backend `/search` SSE endpoint.

**What calls it:** `ResultsPage.tsx` on mount.

---

## frontend/src/api/orders.ts

**What it does:** Two thin wrappers: `getOrders()` → `GET /orders` → `Order[]`; `createOrder(body)` → `POST /orders` → `Order`.

**External services:** Backend `/orders` endpoints.

**What calls it:** `OrderConfirm.tsx` (create), `OrdersPage.tsx` (list).

---

## frontend/src/api/vin.ts

**What it does:** `decodeVin(vin)` calls `GET /vin/{vin}` and returns a `VINSpec` or `null` on any error. Used on input blur to show vehicle confirmation without blocking the user.

**External services:** Backend `/vin/{vin}` endpoint.

**What calls it:** `SearchBar.tsx` on VIN input blur.

---

## frontend/src/api/vendors.ts

**What it does:** Single function `getVendorsForPart(part_id)` — calls `GET /vendors/part/{part_id}` and returns `VendorPart[]`.

**External services:** Backend `/vendors/part/{part_id}` endpoint.

**What calls it:** `VendorSelector` component on mount.

---

## frontend/src/api/procurement.ts

**What it does:** Eight typed wrappers covering the full job lifecycle: `createProcurementJob`, `getProcurementJobs`, `getProcurementJob`, `sendOutreach` (accepts an optional edited outreach email, sent as `{outreach_email}` so operator edits are persisted), `sendFollowup` (accepts optional edited email body), `confirmParsedFields`, `acceptJob`, `rejectJob`. All use `apiGet`/`apiPost` from `client.ts`.

**External services:** Backend `/procurement/*` endpoints.

**What calls it:** `ResultsPage` (create), `OutreachConfirm` (send), `VendorOutreachPanel` (followup, confirm, accept, reject), `ProcurementBoard` (list).
