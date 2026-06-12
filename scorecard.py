"""
稀缺度评分卡 — 从 SQLite 读指标,绝对基线打分,写入 scorecard 表 + scorecard.csv

打分对象:watchlist 各品牌 + 有 series 标签的子集(如 Number (N)ine AW03)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import yaml

from lib import db
from lib.scoring import WEIGHTS, compute_scarcity_scores, score_momentum


def _sep(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print('─'*55)


def load_watchlist(path: str = "watchlist.yaml") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["brands"]


def _listing_filter(brand: str, series: str | None) -> tuple[str, list]:
    if series:
        return (
            "brand=? AND is_active=1 AND suspect_mislabel=0 AND series=?",
            [brand, series],
        )
    return (
        "brand=? AND is_active=1 AND suspect_mislabel=0",
        [brand],
    )


def _sold_filter(brand: str, series: str | None, cutoff: str) -> tuple[str, list]:
    if series:
        return (
            "brand=? AND suspect_mislabel=0 AND sold_at >= ? AND series=?",
            [brand, cutoff, series],
        )
    return (
        "brand=? AND suspect_mislabel=0 AND sold_at >= ?",
        [brand, cutoff],
    )


def fetch_supply(conn: sqlite3.Connection, brand: str, series: str | None) -> int:
    where, params = _listing_filter(brand, series)
    row = conn.execute(f"SELECT COUNT(*) FROM listings WHERE {where}", params).fetchone()
    return int(row[0])


def fetch_demand_30d(conn: sqlite3.Connection, brand: str, series: str | None) -> int:
    cutoff = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    where, params = _sold_filter(brand, series, cutoff)
    row = conn.execute(f"SELECT COUNT(*) FROM sold_records WHERE {where}", params).fetchone()
    return int(row[0])


def fetch_avg_hearts(conn: sqlite3.Connection, brand: str, series: str | None) -> float:
    where, params = _listing_filter(brand, series)
    row = conn.execute(
        f"SELECT AVG(hearts) FROM listings WHERE {where} AND hearts IS NOT NULL",
        params,
    ).fetchone()
    return float(row[0] or 0.0)


def fetch_momentum_medians(
    conn: sqlite3.Connection, brand: str, series: str | None
) -> tuple[float | None, float | None, bool]:
    """listing_events 近 7 天 vs 前 7 天中位价。不足 14 天事件 → 数据不足。"""
    today = datetime.today()
    recent_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    prior_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    prior_end = recent_start

    if series:
        join_filter = "l.brand=? AND l.suspect_mislabel=0 AND l.series=?"
        params_base = [brand, series]
    else:
        join_filter = "l.brand=? AND l.suspect_mislabel=0"
        params_base = [brand]

    def _medians(start: str, end: str | None) -> float | None:
        if end:
            sql = f"""
                SELECT le.price_usd FROM listing_events le
                JOIN listings l ON le.source=l.source AND le.listing_id=l.listing_id
                WHERE {join_filter}
                  AND le.event_date >= ? AND le.event_date < ?
                  AND le.price_usd IS NOT NULL
            """
            prices = [r[0] for r in conn.execute(sql, params_base + [start, end]).fetchall()]
        else:
            sql = f"""
                SELECT le.price_usd FROM listing_events le
                JOIN listings l ON le.source=l.source AND le.listing_id=l.listing_id
                WHERE {join_filter}
                  AND le.event_date >= ?
                  AND le.price_usd IS NOT NULL
            """
            prices = [r[0] for r in conn.execute(sql, params_base + [start]).fetchall()]
        if not prices:
            return None
        return float(pd.Series(prices).median())

    prior_median = _medians(prior_start, prior_end)
    recent_median = _medians(recent_start, None)

    # 至少需要前一周有数据才能算环比
    insufficient = prior_median is None or recent_median is None
    return recent_median, prior_median, insufficient


def score_target(
    conn: sqlite3.Connection,
    brand: str,
    keyword: str,
    series: str | None,
    calc_date: str,
) -> dict:
    supply = fetch_supply(conn, brand, series)
    demand = fetch_demand_30d(conn, brand, series)
    avg_hearts = fetch_avg_hearts(conn, brand, series)
    price_recent, price_prior, momentum_insufficient = fetch_momentum_medians(
        conn, brand, series
    )

    if momentum_insufficient:
        mom_score, price_momentum = 5.0, None
    else:
        mom_score, price_momentum = score_momentum(price_recent, price_prior)

    scores = compute_scarcity_scores(
        supply,
        demand,
        avg_hearts,
        momentum_score=mom_score,
        price_recent=price_recent,
        price_prior=price_prior,
        price_momentum=price_momentum,
    )

    row = {
        "keyword": keyword,
        "brand": brand,
        "series": series,
        "momentum_insufficient": 1 if momentum_insufficient else 0,
        "calc_date": calc_date,
        **scores,
    }
    return row


def build_scorecard(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    own_conn = conn is None
    if own_conn:
        conn = db.connect()

    calc_date = datetime.today().strftime("%Y-%m-%d")
    targets: list[tuple[str, str, str | None]] = []

    for cfg in load_watchlist():
        brand = cfg["name"]
        targets.append((brand, brand, None))
        for series_name in (cfg.get("series") or {}):
            keyword = f"{brand} {series_name}"
            targets.append((brand, keyword, series_name))

    _sep(f"从 SQLite 计算 {len(targets)} 个打分对象")
    rows = []
    for brand, keyword, series in targets:
        row = score_target(conn, brand, keyword, series, calc_date)
        rows.append(row)
        mom_note = " (动量:数据积累中→5.0)" if row["momentum_insufficient"] else ""
        print(
            f"  {keyword:<32} 供给={row['supply_count']:>6,}  "
            f"30d成交={row['demand_count_30d']:>4,}  "
            f"总分={row['total_score']:.2f}{mom_note}"
        )

    df = pd.DataFrame(rows)
    df["rank"] = df["total_score"].rank(ascending=False, method="min").astype(int)
    df = df.sort_values("total_score", ascending=False).reset_index(drop=True)

    _sep("⑤ 加权总分")
    print(f"  权重配置: {WEIGHTS}")
    for _, row in df.iterrows():
        print(f"\n  [{row['rank']}] {row['keyword']}")
        print(f"      ──→ 总分 = {row['total_score']}")

    db.upsert_scorecard(conn, df.to_dict("records"))

    csv_cols = [
        "keyword", "brand", "series", "supply_count", "demand_count_30d",
        "supply_demand_ratio", "supply_demand_score", "velocity_30d",
        "velocity_score", "avg_followers", "grailed_hype_score",
        "price_recent", "price_prior", "price_momentum",
        "price_momentum_score", "total_score", "rank", "calc_date",
    ]
    df[csv_cols].to_csv("scorecard.csv", index=False, encoding="utf-8-sig")

    print(f"\n\n{'═'*55}")
    print("  最终稀缺度排行榜")
    print(f"{'═'*55}")
    print(
        df[["rank", "keyword", "total_score", "supply_demand_ratio",
            "velocity_30d", "avg_followers"]].to_string(index=False)
    )
    print("\n✅ scorecard 表 + scorecard.csv 已保存")

    if own_conn:
        conn.close()
    return df


if __name__ == "__main__":
    build_scorecard()
