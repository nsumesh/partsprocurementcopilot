import re

_DELIVERY_CEILING_HOURS = 480  # 20 days

# Ordered most-specific first so "next business day" beats "day"
_DELIVERY_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r'same.?day|within.?(\d+)\s*hour', re.I),          2),
    (re.compile(r'next.?business.?day|1\s*business\s*day',  re.I), 24),
    (re.compile(r'(\d+)\s*hour',                            re.I), 1),     # multiplier below
    (re.compile(r'(\d+)\s*-\s*(\d+)\s*business\s*day',     re.I), 24),    # range × avg × 24
    (re.compile(r'(\d+)\s*business\s*day',                  re.I), 24),    # n days × 24
    (re.compile(r'(\d+)\s*-\s*(\d+)\s*day',                re.I), 24),    # range × avg × 24
    (re.compile(r'(\d+)\s*week',                            re.I), 168),   # n weeks × 168
    (re.compile(r'(\d+)\s*day',                             re.I), 24),    # n days × 24
]


def delivery_text_to_hours(text: str | None) -> int | None:
    if not text:
        return None
    for pattern, multiplier in _DELIVERY_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        groups = [g for g in m.groups() if g is not None]
        if not groups:
            return multiplier  # fixed value (same-day, next business day)
        if len(groups) == 2:
            avg = (int(groups[0]) + int(groups[1])) / 2
            return max(1, int(avg * multiplier))
        return max(1, int(groups[0]) * multiplier)
    return None


def compute_ranking_score(
    unit_price: float,
    delivery_hours: int,
    response_rate: float,
    max_catalog_price: float = 500.0,
) -> float:
    price_score = 1.0 - (unit_price / max_catalog_price)
    delivery_score = 1.0 - (delivery_hours / _DELIVERY_CEILING_HOURS)
    score = (0.4 * price_score) + (0.4 * delivery_score) + (0.2 * response_rate)
    return max(0.0, min(1.0, score))
