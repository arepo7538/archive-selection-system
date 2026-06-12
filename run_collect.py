"""
采集管道入口 — watchlist 品牌级全量采集 → 本地分类 → 质量门禁 → SQLite

用法
----
python run_collect.py                          # 全部 watchlist 品牌(在售+已售)
python run_collect.py --brand "Number (N)ine"  # 单品牌
python run_collect.py --skip-sold              # 只采在售
python run_collect.py --days 90                # 已售回填窗口(默认 180 天)

每周跑一次(cron / GitHub Actions)。质量门禁:任一品牌抓取量比上次成功
运行暴跌 50% 以上 → 该品牌本轮拒绝落盘并报警,退出码非 0。
"""

import sys
import time
import argparse
from datetime import datetime

import yaml

from lib import db
from lib.classify import classify_rows
from collectors import grailed

BRAND_GAP_SECONDS = 2   # 品牌之间停顿,礼貌限速


def load_watchlist(path: str = "watchlist.yaml") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["brands"]


def collect_brand(conn, cfg: dict, fetch_date: str, *,
                  skip_sold: bool, days: int) -> dict:
    """采集单个品牌(在售 + 已售),返回汇总信息。"""
    brand = cfg["name"]
    summary = {"brand": brand}

    # ── 在售 ─────────────────────────────────────────────
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows, nb_total, stats = grailed.fetch_brand_listings(cfg)
    classify_rows(rows, cfg)

    ok, prev = db.gate_check(conn, "grailed", brand, "listings", len(rows))
    if not ok:
        print(f"  🚫 [{brand}] 质量门禁:本次 {len(rows)} 条 < 上次 {prev} 条的 50%,拒绝落盘")
        db.record_run(conn, source="grailed", brand=brand, kind="listings",
                      started_at=started, rows_fetched=len(rows), rows_written=0,
                      requests=stats.requests, errors=stats.errors,
                      status="rejected_by_gate", note=f"prev={prev}")
        summary["listings"] = "REJECTED"
        return summary

    n_new, n_changed = db.upsert_listings(conn, rows, fetch_date)
    n_gone = db.mark_delisted(conn, "grailed", brand, fetch_date)
    db.record_run(conn, source="grailed", brand=brand, kind="listings",
                  started_at=started, rows_fetched=len(rows),
                  rows_written=n_new + n_changed,
                  requests=stats.requests, errors=stats.errors,
                  status="ok", note=f"platform_total={nb_total}")
    n_suspect = sum(r["suspect_mislabel"] for r in rows)
    summary["listings"] = (f"{len(rows):,} 条(新 {n_new:,} / 变动 {n_changed:,} / "
                           f"下架 {n_gone:,} / 错标嫌疑 {n_suspect:,}")
    print(f"  ✅ [{brand}] 在售入库:{summary['listings']})")

    # ── 已售 ─────────────────────────────────────────────
    if skip_sold:
        return summary

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sold_rows, sstats = grailed.fetch_brand_sold(cfg, days=days)
    classify_rows(sold_rows, cfg)

    ok, prev = db.gate_check(conn, "grailed", brand, "sold", len(sold_rows))
    if not ok:
        print(f"  🚫 [{brand}] 已售质量门禁:本次 {len(sold_rows)} < 上次 {prev} 的 50%,拒绝落盘")
        db.record_run(conn, source="grailed", brand=brand, kind="sold",
                      started_at=started, rows_fetched=len(sold_rows), rows_written=0,
                      requests=sstats.requests, errors=sstats.errors,
                      status="rejected_by_gate", note=f"prev={prev}")
        summary["sold"] = "REJECTED"
        return summary

    n_sold = db.insert_sold(conn, sold_rows)
    db.record_run(conn, source="grailed", brand=brand, kind="sold",
                  started_at=started, rows_fetched=len(sold_rows), rows_written=n_sold,
                  requests=sstats.requests, errors=sstats.errors, status="ok")
    summary["sold"] = f"{len(sold_rows):,} 条(新增 {n_sold:,})"
    print(f"  ✅ [{brand}] 已售入库:{summary['sold']}")
    return summary


def main():
    # 管道/重定向下也逐行输出进度(否则 Python 块缓冲,看起来像卡死)
    sys.stdout.reconfigure(line_buffering=True)

    ap = argparse.ArgumentParser(description="Grailed 品牌级采集管道")
    ap.add_argument("--brand", help="只采集这个品牌(watchlist 中的 name)")
    ap.add_argument("--skip-sold", action="store_true", help="跳过已售采集")
    ap.add_argument("--days", type=int, default=180, help="已售回填窗口天数")
    args = ap.parse_args()

    brands = load_watchlist()
    if args.brand:
        brands = [b for b in brands if b["name"] == args.brand]
        if not brands:
            sys.exit(f"watchlist.yaml 中找不到品牌:{args.brand}")

    conn = db.connect()
    fetch_date = datetime.today().strftime("%Y-%m-%d")
    print(f"{'═'*60}\n  采集开始 {fetch_date} — {len(brands)} 个品牌\n{'═'*60}")

    summaries, rejected = [], False
    for i, cfg in enumerate(brands):
        print(f"\n── [{i+1}/{len(brands)}] {cfg['name']} ──")
        try:
            s = collect_brand(conn, cfg, fetch_date,
                              skip_sold=args.skip_sold, days=args.days)
        except Exception as e:
            print(f"  ❌ [{cfg['name']}] 采集失败:{e}")
            s = {"brand": cfg["name"], "listings": f"FAILED: {e}"}
            db.record_run(conn, source="grailed", brand=cfg["name"], kind="listings",
                          started_at=fetch_date, rows_fetched=0, rows_written=0,
                          requests=0, errors=1, status="failed", note=str(e))
        summaries.append(s)
        rejected |= "REJECTED" in str(s.values()) or "FAILED" in str(s.values())
        if i < len(brands) - 1:
            time.sleep(BRAND_GAP_SECONDS)

    print(f"\n{'═'*60}\n  采集汇总\n{'═'*60}")
    for s in summaries:
        print(f"  {s['brand']:<22} 在售: {s.get('listings','—')}")
        if "sold" in s:
            print(f"  {'':<22} 已售: {s['sold']}")

    conn.close()
    if rejected:
        print("\n⚠️  存在被门禁拒绝或失败的品牌,请检查 pipeline_runs 表")
        sys.exit(1)
    print("\n✅ 全部完成,数据已写入 data/market.db")


if __name__ == "__main__":
    main()
