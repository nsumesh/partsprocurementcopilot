import asyncio
import json
import sys
import time
from typing import Any

import httpx

API_BASE = "http://localhost:8000"

GOLDEN_QUERIES = [
    {
        "vin": "1XKAD49X1EJ391052",
        "query": "oil filter",
        "urgency": "standard",
        "expect_clarify": False,
        "label": "Kenworth T680 — oil filter",
    },
    {
        "vin": "3AKJGLD58FSGF7432",
        "query": "fuel filter replacement",
        "urgency": "standard",
        "expect_clarify": False,
        "label": "Freightliner Cascadia — fuel filter",
    },
    {
        "vin": "4V4NC9EH9EN157361",
        "query": "need brakes",
        "urgency": "standard",
        "expect_clarify": True,
        "label": "Volvo VNL — ambiguous brake query",
    },
    {
        "vin": "1NPXGGGG8FD349872",
        "query": "air filter",
        "urgency": "standard",
        "expect_clarify": False,
        "label": "Peterbilt 386 — air filter",
    },
    {
        "vin": "1M1AW07Y2GM001234",
        "query": "slack adjuster",
        "urgency": "urgent",
        "expect_clarify": False,
        "label": "Mack Pinnacle — slack adjuster (urgent)",
    },
]


async def _collect_sse(
    client: httpx.AsyncClient,
    vin: str,
    query: str,
    urgency: str,
) -> dict[str, Any]:
    parts: list[dict] = []
    clarify_question: str | None = None
    start = time.monotonic()

    async with client.stream(
        "POST",
        f"{API_BASE}/search",
        json={"vin": vin, "query": query, "urgency": urgency},
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[len("data:"):].strip()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "part":
                parts.append(event)
            elif etype == "clarify":
                clarify_question = event.get("question")
            elif etype in ("done", "error"):
                break

    return {
        "parts": parts,
        "clarify_question": clarify_question,
        "clarify_triggered": clarify_question is not None,
        "latency_ms": int((time.monotonic() - start) * 1000),
    }


async def run_eval() -> None:
    print("Parts Procurement Copilot — Eval Runner")
    print("=" * 70)

    rows = []
    all_pass = True

    async with httpx.AsyncClient(timeout=120.0) as client:
        for case in GOLDEN_QUERIES:
            print(f"  Running: {case['label']!r}")
            try:
                result = await _collect_sse(
                    client, case["vin"], case["query"], case["urgency"]
                )
            except Exception as exc:
                print(f"    ERROR: {exc}")
                rows.append({**case, "status": "ERROR", "latency_ms": 0, "parts_count": 0})
                all_pass = False
                continue

            clarify_ok = result["clarify_triggered"] == case["expect_clarify"]
            has_output = len(result["parts"]) > 0 or result["clarify_triggered"]
            passed = clarify_ok and has_output

            if not passed:
                all_pass = False

            rows.append({
                "vin": case["vin"],
                "label": case["label"],
                "urgency": case["urgency"],
                "parts_count": len(result["parts"]),
                "clarify_triggered": result["clarify_triggered"],
                "clarify_expected": case["expect_clarify"],
                "clarify_ok": clarify_ok,
                "latency_ms": result["latency_ms"],
                "status": "PASS" if passed else "FAIL",
            })

    print()
    print(f"{'Label':<40} {'Parts':>5} {'Clarify':>7} {'Latency':>9} {'Status':>6}")
    print("-" * 72)
    for r in rows:
        print(
            f"{r['label']:<40} "
            f"{r['parts_count']:>5} "
            f"{str(r['clarify_triggered']):>7} "
            f"{r['latency_ms']:>8}ms "
            f"{r['status']:>6}"
        )

    print()
    passed_count = sum(1 for r in rows if r["status"] == "PASS")
    print(f"Result: {passed_count}/{len(rows)} passed")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(run_eval())
