import csv
import json
from pathlib import Path

import anthropic


async def generate_aftermarket_csv(
    oe_parts: list[dict],
    api_key: str,
    output_path: str = "data/aftermarket.csv",
) -> str:
    categories = sorted({p["category"] for p in oe_parts if p.get("category")})
    client = anthropic.AsyncAnthropic(api_key=api_key)
    all_rows: list[dict] = []

    for category in categories:
        sample = [p for p in oe_parts if p.get("category") == category][:3]
        prompt = (
            f"Generate 4 realistic aftermarket parts for category: {category}\n\n"
            f"Reference OE parts:\n{json.dumps(sample, indent=2)}\n\n"
            "Return a JSON array of exactly 4 objects with these fields:\n"
            "- part_number: realistic aftermarket SKU (e.g. AF-12345)\n"
            "- name: descriptive part name\n"
            "- description: 1-2 sentence description\n"
            f'- category: "{category}"\n'
            "- brand: aftermarket brand (FleetPro, TruckMaster, RoadKing, or DuraFleet)\n"
            "- price_usd: realistic number\n"
            "- fit_notes: object with make, model, engine, year_range, notes fields\n"
            "- attributes: object with relevant specs\n"
            "- vendor_urls: []\n\n"
            "Return only the JSON array, no markdown."
        )

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()
        try:
            rows = json.loads(text)
            for row in rows:
                row["source"] = "aftermarket"
                all_rows.append(row)
        except json.JSONDecodeError:
            print(f"  Warning: failed to parse aftermarket response for {category!r}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "part_number", "name", "description", "category", "source",
        "brand", "price_usd", "fit_notes", "attributes", "vendor_urls",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            for field in ("fit_notes", "attributes", "vendor_urls"):
                if isinstance(row.get(field), (dict, list)):
                    row[field] = json.dumps(row[field])
            writer.writerow(row)

    print(f"  Aftermarket CSV written: {output_path} ({len(all_rows)} parts)")
    return output_path
