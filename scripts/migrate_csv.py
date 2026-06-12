"""
一次性迁移:旧 CSV → data/market.db

  grailed_listings.csv  → listings(is_active=0,历史观测)+ listing_events(历史价格点)
  grailed_sold.csv      → sold_records
  historical_sold.csv   → sold_records

迁移后旧 CSV 原样保留(只读不删)。当前在售状态由首轮 run_collect.py 刷新。
用法:python scripts/migrate_csv.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from lib import db
from lib.classify import classify_title
from run_collect import load_watchlist


def _brand_for(keyword: str, brands: list[dict]) -> dict | None:
    """旧 keyword(如 'Number Nine AW03')→ watchlist 品牌条目。"""
    kw = str(keyword).lower()
    for cfg in brands:
        if any(tok.lower() in kw for tok in cfg["title_tokens"]):
            return cfg
    return None


def _day(value) -> str | None:
    """ISO 时间戳 / 日期字符串 → YYYY-MM-DD。"""
    ts = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(ts) else ts.strftime("%Y-%m-%d")


def migrate_listings(conn, brands) -> tuple[int, int]:
    path = os.path.join(BASE_DIR, "grailed_listings.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    cur, n_rows, n_skipped = conn.cursor(), 0, 0

    for r in df.itertuples():
        cfg = _brand_for(r.keyword, brands)
        if cfg is None:
            n_skipped += 1
            continue
        tags = classify_title(str(r.title), cfg)
        lid = str(r.listing_id)
        fetch_day = _day(r.fetch_date)
        cur.execute(
            """INSERT OR IGNORE INTO listings
               (source, listing_id, brand, title, category, item_type, series,
                condition, size, seller_location, currency, price_usd, hearts,
                heat_f, url, created_at, first_seen, last_seen, is_active,
                suspect_mislabel)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
            ("grailed", lid, cfg["name"], r.title, r.category,
             tags["item_type"], tags["series"], r.condition, "", "",
             "USD", r.price_usd, r.followers, None,
             f"https://www.grailed.com/listings/{lid}",
             _day(r.created_at), fetch_day, fetch_day,
             tags["suspect_mislabel"]),
        )
        n_rows += cur.rowcount
        cur.execute(
            """INSERT OR IGNORE INTO listing_events
               (source, listing_id, event_date, price_usd, hearts)
               VALUES (?,?,?,?,?)""",
            ("grailed", lid, fetch_day, r.price_usd, r.followers),
        )
    conn.commit()
    return n_rows, n_skipped


def migrate_sold(conn, brands, filename: str) -> tuple[int, int]:
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return 0, 0
    df = pd.read_csv(path, encoding="utf-8-sig")
    rows, n_skipped = [], 0

    for r in df.itertuples():
        cfg = _brand_for(r.keyword, brands)
        if cfg is None:
            n_skipped += 1
            continue
        tags = classify_title(str(r.title), cfg)
        created, sold = _day(r.created_at), _day(r.sold_at)
        days = None
        if created and sold:
            days = (pd.to_datetime(sold) - pd.to_datetime(created)).days
        rows.append({
            "source": "grailed", "listing_id": str(r.listing_id),
            "brand": cfg["name"], "title": r.title,
            "category": getattr(r, "category", ""),
            "item_type": tags["item_type"], "series": tags["series"],
            "condition": getattr(r, "condition", ""), "size": "",
            "seller_location": "",
            "sold_price_usd": r.sold_price, "price_includes_shipping": None,
            "created_at": created, "sold_at": sold, "days_to_sell": days,
            "suspect_mislabel": tags["suspect_mislabel"],
            "fetch_date": _day(r.fetch_date),
        })
    return db.insert_sold(conn, rows), n_skipped


def main():
    brands = load_watchlist(os.path.join(BASE_DIR, "watchlist.yaml"))
    conn = db.connect()

    n, skipped = migrate_listings(conn, brands)
    print(f"grailed_listings.csv   → listings: 新增 {n:,} 条(无法映射品牌跳过 {skipped})")

    for f in ["grailed_sold.csv", "historical_sold.csv"]:
        n, skipped = migrate_sold(conn, brands, f)
        print(f"{f:<22} → sold_records: 新增 {n:,} 条(跳过 {skipped})")

    total_l = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    total_s = conn.execute("SELECT COUNT(*) FROM sold_records").fetchone()[0]
    print(f"\n迁移完成:listings 共 {total_l:,} 行,sold_records 共 {total_s:,} 行")
    conn.close()


if __name__ == "__main__":
    main()
