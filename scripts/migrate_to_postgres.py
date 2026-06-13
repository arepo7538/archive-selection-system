"""
一次性迁移:本地 SQLite(data/market.db)→ Supabase/Postgres

  python scripts/migrate_to_postgres.py

前提:.env 里已配置 DATABASE_URL。幂等(ON CONFLICT DO NOTHING),可重复跑。
pipeline_runs 的自增 run_id 不迁移(由 PG SERIAL 按插入顺序重新分配,保持相对先后)。
"""

from __future__ import annotations

import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from lib import db

TABLES = ["listings", "listing_events", "sold_records",
          "scorecard", "brand_heat", "candidates", "pipeline_runs"]


def main():
    if not db.IS_POSTGRES:
        sys.exit("❌ 未检测到 DATABASE_URL,无法迁移。请先在 .env 配置。")

    import psycopg2
    from psycopg2.extras import execute_values

    if not os.path.exists(db.DB_PATH):
        sys.exit(f"❌ 本地 SQLite 不存在:{db.DB_PATH}")

    slite = sqlite3.connect(db.DB_PATH)
    slite.row_factory = sqlite3.Row

    db.connect().close()                       # 确保 PG 表已建好
    pg = psycopg2.connect(db.DATABASE_URL, connect_timeout=20)
    pgcur = pg.cursor()

    print(f"{'═'*56}\n  SQLite → Postgres 迁移\n{'═'*56}")
    for table in TABLES:
        # SQLite 实际列(老库可能缺 hearts 等新列)
        cols = [r[1] for r in slite.execute(f"PRAGMA table_info({table})")]
        if table == "pipeline_runs" and "run_id" in cols:
            cols.remove("run_id")              # 让 PG SERIAL 重新分配
        if not cols:
            print(f"  {table:<16} 跳过(本地无此表)")
            continue

        order = " ORDER BY run_id" if table == "pipeline_runs" else ""
        rows = slite.execute(
            f"SELECT {', '.join(cols)} FROM {table}{order}"
        ).fetchall()
        if not rows:
            print(f"  {table:<16} 0 行")
            continue

        data = [tuple(r) for r in rows]
        sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
               f"VALUES %s ON CONFLICT DO NOTHING")
        execute_values(pgcur, sql, data, page_size=1000)
        pg.commit()

        pgcur.execute(f"SELECT COUNT(*) FROM {table}")
        cnt = pgcur.fetchone()[0]
        print(f"  {table:<16} 本地 {len(data):>7,} → PG 现有 {cnt:>7,}")

    slite.close()
    pg.close()
    print("\n✅ 迁移完成。今后只要 .env 有 DATABASE_URL,所有读写都走 Supabase。")


if __name__ == "__main__":
    main()
