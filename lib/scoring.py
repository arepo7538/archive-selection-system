"""
稀缺度打分 — 绝对 log 基线(单一事实来源)

权重: S/D 35% · Velocity 30% · Hype 25% · Momentum 10%
与 agent calculate_scarcity_score 口径一致;momentum 缺数据时中性 5.0。
"""

from __future__ import annotations

import math

WEIGHTS = {
    "supply_demand_score": 0.35,
    "velocity_score": 0.30,
    "grailed_hype_score": 0.25,
    "price_momentum_score": 0.10,
}


def score_supply_demand(supply_count: int, demand_count_30d: int) -> tuple[float, float]:
    """返回 (supply_demand_ratio, supply_demand_score)。"""
    demand = max(demand_count_30d, 1)
    ratio = supply_count / demand
    sd_score = max(0.0, min(10.0, 10.0 - math.log1p(ratio) * 2.2))
    return round(ratio, 2), round(sd_score, 2)


def score_velocity(demand_count_30d: int) -> float:
    return round(min(10.0, math.log1p(demand_count_30d) / math.log1p(200) * 10), 2)


def score_hype(avg_followers: float) -> float:
    return round(min(10.0, math.log1p(avg_followers) / math.log1p(50) * 10), 2)


def score_momentum(price_recent: float | None, price_prior: float | None) -> tuple[float, float | None]:
    """
    周环比中位价 → 动量分。数据不足返回 (5.0, None)。
    第二返回值 price_momentum 为小数涨跌幅(非百分数)。
    """
    if price_prior is None or price_prior <= 0 or price_recent is None:
        return 5.0, None
    pct = (price_recent - price_prior) / price_prior
    mom_score = max(0.0, min(10.0, 5.0 + pct * 10))
    return round(mom_score, 2), round(pct, 4)


def compute_scarcity_scores(
    supply_count: int,
    demand_count_30d: int,
    avg_followers: float,
    *,
    momentum_score: float = 5.0,
    price_recent: float | None = None,
    price_prior: float | None = None,
    price_momentum: float | None = None,
) -> dict:
    """计算四维分数与加权总分。"""
    ratio, sd_score = score_supply_demand(supply_count, demand_count_30d)
    vel_score = score_velocity(demand_count_30d)
    hype_score = score_hype(avg_followers)

    total = (
        sd_score * WEIGHTS["supply_demand_score"]
        + vel_score * WEIGHTS["velocity_score"]
        + hype_score * WEIGHTS["grailed_hype_score"]
        + momentum_score * WEIGHTS["price_momentum_score"]
    )

    return {
        "supply_count": supply_count,
        "demand_count_30d": demand_count_30d,
        "supply_demand_ratio": ratio,
        "supply_demand_score": sd_score,
        "velocity_30d": demand_count_30d,
        "velocity_score": vel_score,
        "avg_followers": round(avg_followers, 4),
        "grailed_hype_score": hype_score,
        "price_recent": price_recent,
        "price_prior": price_prior,
        "price_momentum": price_momentum,
        "price_momentum_score": momentum_score,
        "total_score": round(total, 2),
    }


def compute_scarcity_scores_for_agent(
    supply_count: int,
    demand_count_30d: int,
    avg_followers: float,
) -> dict:
    """agent 工具专用:无历史 snapshot,momentum 固定中性 5.0。"""
    scores = compute_scarcity_scores(
        supply_count, demand_count_30d, avg_followers, momentum_score=5.0
    )
    return {
        "supply_demand_ratio": scores["supply_demand_ratio"],
        "supply_demand_score": scores["supply_demand_score"],
        "velocity_score": scores["velocity_score"],
        "hype_score": scores["grailed_hype_score"],
        "momentum_score": 5.0,
        "total_score": scores["total_score"],
        "score_breakdown": {
            "supply_demand": (
                f"{scores['supply_demand_score']:.1f}/10  "
                f"(ratio={scores['supply_demand_ratio']:.1f}, "
                f"supply={supply_count}, demand_30d={demand_count_30d})"
            ),
            "velocity": (
                f"{scores['velocity_score']:.1f}/10  "
                f"(demand_30d={demand_count_30d})"
            ),
            "hype": (
                f"{scores['grailed_hype_score']:.1f}/10  "
                f"(avg_followers={avg_followers})"
            ),
            "momentum": "5.0/10  (N/A – single snapshot)",
        },
    }
