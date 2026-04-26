import re

from browserbase import Browserbase
from playwright.async_api import async_playwright

from app.config import Settings

_CATEGORIES = [
    "oil filter heavy truck",
    "fuel filter heavy truck",
    "air filter heavy duty truck",
    "radiator heavy truck",
    "slack adjuster truck",
    "brake shoe heavy truck",
    "water pump heavy truck",
    "thermostat heavy truck",
    "wheel seal heavy truck",
    "drive belt heavy truck",
]

_BASE_URL = "https://www.finditparts.com"

_CATEGORY_MAP = {
    "oil filter": "oil_filter",
    "fuel filter": "fuel_filter",
    "air filter": "air_filter",
    "radiator": "radiator",
    "slack adjuster": "slack_adjuster",
    "brake shoe": "brake",
    "water pump": "water_pump",
    "thermostat": "thermostat",
    "wheel seal": "wheel_seal",
    "drive belt": "drive_belt",
}


async def scrape_oe_parts(settings: Settings) -> list[dict]:
    bb = Browserbase(api_key=settings.browserbase_api_key)
    session = bb.sessions.create(project_id=settings.browserbase_project_id)
    ws_url = (
        f"wss://connect.browserbase.com"
        f"?apiKey={settings.browserbase_api_key}&sessionId={session.id}"
    )

    parts: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws_url)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await ctx.new_page()

        # Load homepage — search form lives in the persistent header
        await page.goto(_BASE_URL, wait_until="networkidle", timeout=30_000)
        await _dismiss_popup(page)

        for category_query in _CATEGORIES:
            try:
                category_parts = await _scrape_category(page, category_query)
                parts.extend(category_parts)
                print(f"    {category_query}: {len(category_parts)} parts")
            except Exception as exc:
                print(f"    Warning: skipping {category_query!r}: {exc}")

        await browser.close()

    return parts


async def _dismiss_popup(page) -> None:
    """Close Klaviyo / modal overlays that intercept pointer events."""
    try:
        await page.wait_for_selector(
            "[aria-label='POPUP Form'], .kl-private-reset-css-Xuajs1",
            timeout=4_000,
        )
        await page.keyboard.press("Escape")
        await page.wait_for_selector(
            "[aria-label='POPUP Form']",
            state="hidden",
            timeout=3_000,
        )
    except Exception:
        pass


async def _scrape_category(page, query: str) -> list[dict]:
    category = _query_to_category(query)

    # Step 1 — fill the search input
    search_input = await page.wait_for_selector("#searcher_s", timeout=8_000)
    await search_input.fill(query)

    # Step 2 — dismiss popup then submit via requestSubmit()
    await _dismiss_popup(page)
    await page.evaluate("""() => {
        const f = document.querySelector('form.fip_header__search_form');
        if (f) f.requestSubmit();
    }""")

    # Step 3 — wait for the loaded grid.
    # Two grids are always in the DOM simultaneously:
    #   .product_results_grid.loading  — skeleton placeholder (never removed)
    #   .product_results_grid.loaded   — actual results (added by AJAX when done)
    # We must wait for the .loaded grid specifically.
    try:
        await page.wait_for_selector(
            ".product_results_grid.loaded", timeout=30_000
        )
    except Exception as exc:
        print(f"    Warning: loaded grid never appeared for {query!r}: {exc}")
        await page.fill("#searcher_s", "")
        return []

    # Step 4 — select cards only from the loaded grid (not the skeleton)
    cards = await page.query_selector_all(".product_results_grid.loaded .product_search_result")

    parts = []
    for i, card in enumerate(cards[:20]):
        try:
            part = await _extract_part(card, category)
            if part:
                parts.append(part)
        except Exception as exc:
            print(f"    Warning: card[{i}] failed for {query!r}: {exc}")

    # Step 5 — clear input before next search term
    await page.fill("#searcher_s", "")

    return parts


async def _extract_part(card, category: str) -> dict | None:
    # Read all needed data in one JS round-trip to avoid stale element references
    # across Turbo frame updates. Description lives in the card, not the anchor.
    data: dict | None = await card.evaluate("""el => {
        const anchor = el.querySelector('.product_search_result_tile_direction a');
        if (!anchor) return null;
        const descEl = el.querySelector('[itemprop="description"]');
        return {
            name:        anchor.getAttribute('data-name')      || '',
            price:       anchor.getAttribute('data-price')     || '',
            brand:       anchor.getAttribute('data-brand')     || '',
            category:    anchor.getAttribute('data-category')  || '',
            category2:   anchor.getAttribute('data-category2') || '',
            href:        anchor.getAttribute('href')           || '',
            description: descEl ? descEl.textContent.trim() : '',
        };
    }""")

    if not data:
        return None

    name = data["name"].strip()
    if not name:
        return None

    brand = data["brand"].strip()

    # Real manufacturer part number: data-name format is "{BRAND} {PART_NUMBER}"
    # Strip the brand prefix to isolate the part number token.
    if brand and name.upper().startswith(brand.upper()):
        part_number = name[len(brand):].strip()
    else:
        part_number = _pn_from_href(data["href"], brand)

    if not part_number:
        part_number = f"FIP-{abs(hash(name)) % 100_000:05d}"

    price_usd: float | None = None
    if data["price"]:
        m = re.search(r"[\d]+\.?\d*", data["price"].replace(",", ""))
        if m:
            try:
                price_usd = float(m.group())
            except ValueError:
                pass

    href = data["href"]
    vendor_url = (_BASE_URL + href) if href.startswith("/") else (href or _BASE_URL)

    return {
        "part_number": part_number,
        "name": name,
        "description": data["description"] or None,
        "category": category,
        "source": "OE",
        "brand": brand or None,
        "price_usd": price_usd,
        "fit_notes": {},
        "attributes": {"category2": data["category2"]} if data["category2"] else {},
        "vendor_urls": [{"vendor": "finditparts.com", "url": vendor_url}],
    }


def _pn_from_href(href: str, brand: str = "") -> str | None:
    """Extract manufacturer part number from the product URL last segment.

    URL pattern: /products/{db_id}/{brand-slug}-{part-number}
    e.g. /products/13888039/allison-29558295 -> 29558295
    """
    if not href:
        return None
    segments = href.rstrip("/").split("/")
    if len(segments) < 2:
        return None
    last_seg = segments[-1]
    if brand:
        brand_slug = brand.lower().replace(" ", "-")
        if last_seg.startswith(brand_slug + "-"):
            return last_seg[len(brand_slug) + 1:].upper()
    # Fallback: last hyphen-separated token that looks like a part number
    for token in reversed(last_seg.split("-")):
        if re.match(r"^[A-Z0-9][A-Z0-9_]*$", token.upper()):
            return token.upper()
    return None


def _query_to_category(query: str) -> str:
    lower = query.lower()
    for key, val in _CATEGORY_MAP.items():
        if key in lower:
            return val
    return "general"
