"""
品牌池漏斗管理器 — L1 提名 → L2 试用浅采集 → L3 晋升/降级建议

  python scripts/universe.py                 # 完整流程
  python scripts/universe.py --min-scans 1   # 降低提名门槛(数据积累初期用)

流程(对应 HANDOFF T6b/T6c):
  1. 提名:brand_heat(discovery 扫描)中连续上榜 ≥ min_scans 次、
     且不在 watchlist 的品牌 → candidates 表(status=probation),facet 自动验证
  2. 试用浅采集:对 probation 品牌每次只发 3 个请求
     (在售总量 / 30 天成交总量 / top100 均收藏+中位价)→ 追加 brand_heat(source=probe)
  3. 晋升判定:试用 ≥ PROBATION_DAYS 且指标达标 → status=ready,
     打印可直接粘贴 watchlist.yaml 的条目。【不自动改 yaml,人工最终拍板】
  4. 降级建议:watchlist 品牌 30 天成交连续走低 → 打印提示(仅建议)

人只保留一票否决权:本脚本只读写 candidates/brand_heat,不碰 watchlist.yaml。
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import pandas as pd

from lib import db
from collectors.grailed import (
    _session, _Stats, _post, _facet_filters,
    INDEX_LISTINGS, INDEX_SOLD, verify_designer_facet,
)
from run_collect import load_watchlist

# ── 晋升门槛(可调)────────────────────────────────────────────
MIN_DEMAND_30D   = 30        # 流动性下限:30 天成交
MIN_SUPPLY       = 1_000     # 规模下限:太小没生意
MAX_SUPPLY       = 60_000    # 规模上限:太大要 query 收窄(参考 Prada)
MIN_MEDIAN_PRICE = 100       # 价格带下限(USD)
MAX_MEDIAN_PRICE = 1_000     # 价格带上限
PROBATION_DAYS   = 14        # 试用期最短天数
DEMOTE_DEMAND    = 10        # 降级线:30 天成交低于此值


def nominate(conn, min_scans: int, min_count: int = 5) -> list[str]:
    """L1→L2:discovery 热度榜常客且未跟踪 → 提名进 candidates。"""
    tracked = set()
    for cfg in load_watchlist(os.path.join(BASE_DIR, "watchlist.yaml")):
        tracked.add(cfg["name"].lower())
        tracked.add(cfg.get("grailed_facet", cfg["name"]).lower())

    rows = conn.execute(
        """SELECT brand, COUNT(DISTINCT scan_date) AS n_scans,
                  AVG(listing_count) AS avg_cnt
           FROM brand_heat WHERE source='discovery'
           GROUP BY brand
           HAVING n_scans >= ? AND avg_cnt >= ?
           ORDER BY avg_cnt DESC""",
        (min_scans, min_count),
    ).fetchall()

    today = datetime.today().strftime("%Y-%m-%d")
    nominated = []
    for brand, n_scans, avg_cnt in rows:
        if brand.lower() in tracked:
            continue
        if conn.execute("SELECT 1 FROM candidates WHERE brand=?", (brand,)).fetchone():
            continue
        check = verify_designer_facet(brand)
        if check["valid"]:
            conn.execute(
                """INSERT INTO candidates (brand, facet_name, nominated_at, status, note)
                   VALUES (?,?,?,'probation',?)""",
                (brand, brand, today,
                 f"上榜{n_scans}次/均{avg_cnt:.0f}条; facet在售{check['nb_hits']:,}"),
            )
            nominated.append(brand)
            print(f"  ✚ 提名 {brand}(上榜 {n_scans} 次,facet 在售 {check['nb_hits']:,} 条)")
        else:
            conn.execute(
                """INSERT INTO candidates (brand, facet_name, nominated_at, status, note)
                   VALUES (?,?,?,'rejected','facet 不存在,需人工确认精确名')""",
                (brand, brand, today),
            )
            print(f"  ✗ {brand}:facet 验证失败,标记 rejected(可能名称写法不同)")
    conn.commit()
    return nominated


def probe(conn) -> None:
    """L2:对 probation 品牌做 3 请求浅采集,追加 brand_heat(source=probe)。"""
    cands = conn.execute(
        "SELECT brand, facet_name FROM candidates WHERE status='probation'"
    ).fetchall()
    if not cands:
        print("  (无试用期品牌)")
        return

    today = datetime.today().strftime("%Y-%m-%d")
    cutoff = int((datetime.now() - timedelta(days=30)).timestamp())
    s = _session()

    for brand, facet in cands:
        stats = _Stats()
        try:
            base = {"query": "", "facetFilters": _facet_filters(facet)}
            supply = _post(s, stats, INDEX_LISTINGS, {**base, "hitsPerPage": 0}).get("nbHits", 0)
            demand = _post(s, stats, INDEX_SOLD,
                           {**base, "hitsPerPage": 0,
                            "numericFilters": json.dumps([f"sold_at_i>={cutoff}"])}
                           ).get("nbHits", 0)
            top = _post(s, stats, INDEX_LISTINGS, {**base, "hitsPerPage": 100}).get("hits", [])
            hearts = [h.get("followerno", 0) for h in top]
            prices = [h.get("price_i") or h.get("price") for h in top
                      if h.get("price_i") or h.get("price")]
            avg_hearts = float(pd.Series(hearts).mean()) if hearts else 0.0
            med_price = float(pd.Series(prices).median()) if prices else None

            conn.execute(
                """INSERT OR REPLACE INTO brand_heat
                   (brand, scan_date, source, avg_hearts, median_price,
                    supply_total, demand_30d)
                   VALUES (?,?,'probe',?,?,?,?)""",
                (brand, today, avg_hearts, med_price, supply, demand),
            )
            conn.execute("UPDATE candidates SET last_check=? WHERE brand=?", (today, brand))
            print(f"  🔍 {brand:<20} 在售={supply:>7,} 30d成交={demand:>5,} "
                  f"中位价=${med_price or 0:>5.0f} 均收藏={avg_hearts:.1f}")
        except Exception as e:
            print(f"  ⚠️  {brand} 浅采集失败:{e}")
    conn.commit()


def _yaml_entry(brand: str, facet: str) -> str:
    token = brand.lower()
    return (
        f'  - name: "{brand}"\n'
        f'    grailed_facet: "{facet}"\n'
        f'    title_tokens: ["{token}"]\n'
        f'    yahoo_query: ""          # TODO: 补日文搜索词\n'
        f'    series: {{}}             # TODO: 按需补系列规则'
    )


def evaluate(conn) -> None:
    """L2→L3:试用期满且指标达标 → ready,打印 yaml 条目。"""
    cands = conn.execute(
        "SELECT brand, facet_name, nominated_at FROM candidates WHERE status='probation'"
    ).fetchall()
    if not cands:
        return

    today = datetime.today()
    for brand, facet, nominated_at in cands:
        days = (today - datetime.strptime(nominated_at, "%Y-%m-%d")).days
        m = conn.execute(
            """SELECT supply_total, demand_30d, median_price FROM brand_heat
               WHERE brand=? AND source='probe'
               ORDER BY scan_date DESC LIMIT 1""",
            (brand,),
        ).fetchone()
        if m is None:
            continue
        supply, demand, med = m
        checks = {
            f"试用≥{PROBATION_DAYS}天": days >= PROBATION_DAYS,
            f"30d成交≥{MIN_DEMAND_30D}": (demand or 0) >= MIN_DEMAND_30D,
            f"在售{MIN_SUPPLY//1000}k~{MAX_SUPPLY//1000}k": MIN_SUPPLY <= (supply or 0) <= MAX_SUPPLY,
            f"中位价${MIN_MEDIAN_PRICE}~{MAX_MEDIAN_PRICE}": med is not None
                and MIN_MEDIAN_PRICE <= med <= MAX_MEDIAN_PRICE,
        }
        failed = [k for k, ok in checks.items() if not ok]
        if not failed:
            conn.execute("UPDATE candidates SET status='ready' WHERE brand=?", (brand,))
            print(f"\n  🎓 {brand} 达标晋升!粘贴以下条目到 watchlist.yaml:\n")
            print(_yaml_entry(brand, facet))
        else:
            print(f"  ⏳ {brand}(试用第 {days} 天)未达标:{' / '.join(failed)}")
    conn.commit()


def demote_check(conn) -> None:
    """L3 降级建议:watchlist 品牌 30 天成交低于降级线 → 打印提示。"""
    rows = conn.execute(
        """SELECT keyword, demand_count_30d, calc_date FROM scorecard
           WHERE series IS NULL AND calc_date = (SELECT MAX(calc_date) FROM scorecard)"""
    ).fetchall()
    flagged = [(k, d) for k, d, _ in rows if (d or 0) < DEMOTE_DEMAND]
    if flagged:
        for k, d in flagged:
            print(f"  📉 {k}:30 天成交仅 {d},连续数周如此可考虑降级(移出深采集)")
    else:
        print("  (watchlist 品牌流动性均高于降级线)")


def main():
    ap = argparse.ArgumentParser(description="品牌池漏斗管理器")
    ap.add_argument("--min-scans", type=int, default=3,
                    help="提名门槛:discovery 上榜次数(默认 3)")
    args = ap.parse_args()

    conn = db.connect()
    print("═" * 60)
    print("  品牌池漏斗 — 提名 / 试用 / 晋升")
    print("═" * 60)

    print(f"\n[1/4] 提名(上榜 ≥{args.min_scans} 次)")
    nominate(conn, args.min_scans)

    print("\n[2/4] 试用期浅采集(3 请求/品牌)")
    probe(conn)

    print("\n[3/4] 晋升判定")
    evaluate(conn)

    print("\n[4/4] watchlist 降级检查")
    demote_check(conn)

    n_p, n_r = conn.execute(
        "SELECT SUM(status='probation'), SUM(status='ready') FROM candidates"
    ).fetchone()
    print(f"\n候选池:试用中 {n_p or 0} / 待晋升 {n_r or 0}(详见 candidates 表)")
    conn.close()


if __name__ == "__main__":
    main()
