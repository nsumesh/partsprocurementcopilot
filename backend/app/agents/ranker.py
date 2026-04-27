_DELIVERY_CEILING_HOURS = 480  # 20 days


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
