"""
对库内数据重跑分类 — 改了 watchlist 规则 / classify 逻辑后执行,无需重爬

  python scripts/reclassify.py

对 listings 与 sold_records 全量重算 series / item_type / suspect_mislabel。
这正是"分类放本地"架构的意义:规则迭代成本 = 跑一遍本脚本(秒级)。
"""

from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from lib import db
from lib.classify import classify_title
from run_collect import load_watchlist


def reclassify_table(conn, table: str, brands: list[dict]) -> int:
    n = 0
    for cfg in brands:
        rows = conn.execute(
            f"SELECT listing_id, source, title FROM {table} WHERE brand=?",
            (cfg["name"],),
        ).fetchall()
        updates = []
        for lid, source, title in rows:
            tags = classify_title(title or "", cfg)
            updates.append((tags["series"], tags["item_type"],
                            tags["suspect_mislabel"], source, lid))
        conn.executemany(
            f"""UPDATE {table} SET series=?, item_type=?, suspect_mislabel=?
                WHERE source=? AND listing_id=?""",
            updates,
        )
        n += len(updates)
    conn.commit()
    return n


def main():
    brands = load_watchlist(os.path.join(BASE_DIR, "watchlist.yaml"))
    conn = db.connect()

    for table in ["listings", "sold_records"]:
        n = reclassify_table(conn, table, brands)
        suspects = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE suspect_mislabel=1").fetchone()[0]
        print(f"{table:<14} 重算 {n:,} 行,当前错标嫌疑 {suspects:,} 条")

    conn.close()
    print("✅ 重分类完成")


if __name__ == "__main__":
    main()
