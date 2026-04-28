# Frontend — Components

## UI Design System

Color tokens: `zinc-950` (page bg), `zinc-900` (cards/panels), `zinc-800` (inputs/elevated), `zinc-700` (borders/toggles), `orange-500` (primary CTA), `orange-400` (hover/accent text), `white`/`zinc-400`/`zinc-500` (text hierarchy). Branding: "HeaviAI Procurement CoPilot" with "Procurement" in orange on the landing page. Applied across all component and page files.

---

## frontend/src/components/SearchBar.tsx

**What it does:** Controlled form with three inputs — VIN (text, 17-char max), query (textarea), and urgency toggle (Standard / Urgent button group). On VIN input blur, calls `decodeVin` and shows the vehicle confirmation ("2014 Kenworth T680 — Paccar MX-13") in orange, or an error in red if the VIN is unrecognized. Submit button is disabled until VIN is exactly 17 characters and query is non-empty. When "Urgent" is selected, `handleSetUrgent()` pre-fills `urgencyDeadline` to now+2h if not already set, and a `datetime-local` input with an orange border appears below the urgency toggle (min attribute recomputed from `minDeadline()` on every render to prevent past dates). On submit, passes `urgency_deadline` as the fourth arg to `onSearch` (null when standard).

**External services:** Backend `GET /vin/{vin}` (via `decodeVin`).

**What calls it:** `SearchPage.tsx`.

---

## frontend/src/components/PartCard.tsx

**What it does:** Renders a single search result as a dark card with fade-in animation on mount (triggered as cards stream in). Displays part name, part number (monospace), category chip, source chip (OEM=blue / Aftermarket=purple), fitment confidence badge (color-coded), and price. The full card is clickable to open the detail panel.

**External services:** None.

**What calls it:** `ResultsPage.tsx` — one card per item in the filtered results array.

---

## frontend/src/components/PartDetail.tsx

**What it does:** Slide-in right panel showing full part detail. Sections: fitment confidence badge + reasoning paragraph, brand + unit price, description, specifications key/value table (from `part.attributes`), vendor sources list (vendor name, link). Two footer buttons: "Order This Part" (`onOrder`) for a simple intent order and "Procure →" (`onProcure`) which kicks off the vendor outreach flow. Rendered on top of a blurred dark backdrop; clicking outside or the X button closes it.

**External services:** None.

**What calls it:** `ResultsPage.tsx` — rendered when `selectedResult` is set.

---

## frontend/src/components/OrderConfirm.tsx

**What it does:** Modal overlay for confirming an order. Shows part name and number, a quantity number input (min 1, default 1), and a live-calculated total (`price × qty`). On confirm, calls `createOrder` to POST to the backend then calls `onConfirm` to navigate to orders. Animated with `fade-up` on mount.

**External services:** Backend `POST /orders` (via `createOrder`).

**What calls it:** `ResultsPage.tsx` — rendered when `confirmTarget` is set.

---

## frontend/src/components/OrderHistory.tsx

**What it does:** Renders all past orders as a dark-themed table. Columns: Part Name, Part Number, Qty, VIN, Urgency (urgent gets an orange badge), Date. Shows an empty-state message when no orders exist. Stateless — receives the `orders` array as a prop.

**External services:** None.

**What calls it:** `OrdersPage.tsx`.

---

## frontend/src/components/FilterPanel.tsx

**What it does:** Renders a filter sidebar with four sections: Source (OEM/Aftermarket checkboxes), Fitment confidence (four confidence levels), Price range (min/max number inputs), and Year range (min/max year inputs, filters by part compatibility range). Exports `FilterState` interface and `DEFAULT_FILTERS` constant used by `ResultsPage`. Stateless — all filter state lives in the parent.

**External services:** None.

**What calls it:** `ResultsPage.tsx` (filter sidebar).

---

## frontend/src/components/VendorSelector.tsx

**What it does:** Modal for selecting a vendor before creating a procurement job. Fetches `VendorPart[]` from `getVendorsForPart` on mount and renders each as a clickable card showing vendor name, type badge, response rate badge (green/yellow/red), ETA, and price. When urgency is `urgent`, renders a datetime-local input pre-filled with `urgencyDeadline` (min = now+2h) and dims vendors whose `delivery_hours` would exceed the deadline with an amber warning. Clicking a card calls `onSelect(vendorPart, deadline)`.

**External services:** Backend `/vendors/part/{part_id}` (via `getVendorsForPart`).

**What calls it:** `ResultsPage` — opened when user clicks "Procure →" in `PartDetail`.

---

## frontend/src/components/OutreachConfirm.tsx

**What it does:** Modal showing the Haiku-generated outreach email in an editable `textarea`. User can edit before sending. "Send Outreach" calls `sendOutreach(job.id)`, which transitions the job to `outreach_sent`. Calls `onConfirm(updatedJob)` on success.

**External services:** Backend `POST /procurement/jobs/{id}/send` (via `sendOutreach`).

**What calls it:** `ResultsPage` — shown after job is created and vendor is selected.

---

## frontend/src/components/VendorOutreachPanel.tsx

**What it does:** Right-side slide-in panel (same pattern as `PartDetail`) showing the full lifecycle of a procurement job. Sections: vendor info card, collapsible outreach email, vendor response email, parsed fields table (missing values shown in amber), follow-up textarea editor when status is `follow_up_required`, ranking score breakdown with three `ScoreBar` sub-components when ranked, Accept/Reject sticky footer when ranked. All actions (send follow-up, accept, reject) call the relevant API function via the shared `act()` helper and propagate the updated job to the parent via `onJobUpdate`.

**External services:** Backend procurement endpoints (via `sendFollowup`, `acceptJob`, `rejectJob`).

**What calls it:** `ProcurementBoard` — opened when a job row is clicked.

---

## frontend/src/components/ProcurementJobRow.tsx

**What it does:** Single table row for the procurement job board. Displays part name + part number, vendor name + type, status badge (color-coded with pulse animation for awaiting states), time elapsed since last event, and a "last action" string derived from the final event in `job.events`. Clicking the row calls `onClick`.

**External services:** None.

**What calls it:** `ProcurementBoard` — one row per job in the jobs table.
