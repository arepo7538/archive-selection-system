"""
Historical Sold Data Scraper
抓取 scorecard Top10 单品过去 180 天的 Grailed 历史成交记录
用于价格预测模型训练

用法: python historical_scraper.py
"""

import os
import requests
import pandas as pd
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Algolia 配置（与 grailed_scraper.py 相同）────────────────────
ALGOLIA_URL = "https://mnrwefss2q-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_PARAMS = {
    "x-algolia-agent": "Algolia for JavaScript (4.14.2); Browser (lite)",
    "x-algolia-api-key": "c89dbaddf15fe70e1941a109bf7c2a3d",
    "x-algolia-application-id": "MNRWEFSS2Q",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ── 抓取参数 ─────────────────────────────────────────────────────
HITS_PER_PAGE = 40
MAX_PAGES = 25          # 最多 1000 条 / 关键词
LOOKBACK_DAYS = 180     # 过去 6 个月
TOP_N = 10              # 取综合得分前 10
SLEEP_PER_PAGE = 1.0    # 每页间隔（秒）
SLEEP_PER_KW = 3.0      # 每个关键词间隔（秒）


def load_top_keywords(n: int = TOP_N) -> list:
    """从 scorecard.csv 读取综合得分 Top N 的关键词"""
    csv_path = os.path.join(BASE_DIR, "scorecard.csv")
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["total_score"])
    df = df.sort_values("total_score", ascending=False)
    keywords = df.head(n)["keyword"].tolist()
    print(f"Loaded Top {len(keywords)} keywords from scorecard.csv:")
    for i, kw in enumerate(keywords, 1):
        score = df[df["keyword"] == kw]["total_score"].values[0]
        print(f"  {i:>2}. {kw}  (score: {score:.2f})")
    return keywords


def _algolia_post(payload: dict) -> dict:
    resp = requests.post(
        ALGOLIA_URL, json=payload, headers=HEADERS,
        params=ALGOLIA_PARAMS, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["results"][0]


def fetch_historical_sold(keyword: str, days: int = LOOKBACK_DAYS) -> list:
    """
    抓取指定关键词过去 N 天的已售记录
    返回 dict 列表，每条包含关键字段
    """
    cutoff_ts = int((datetime.today() - timedelta(days=days)).timestamp())
    results = []
    total_hits = 0

    for page in range(MAX_PAGES):
        params_str = (
            f"query={keyword}"
            f"&page={page}"
            f"&hitsPerPage={HITS_PER_PAGE}"
            f"&numericFilters=sold_at_i%3E{cutoff_ts}"
        )
        payload = {
            "requests": [{
                "indexName": "Listing_sold_production",
                "params": params_str,
            }]
        }

        try:
            result = _algolia_post(payload)

            if page == 0:
                total_hits = result.get("nbHits", 0)
                print(f"  Total matches: {total_hits:,}")

            hits = result.get("hits", [])
            if not hits:
                break

            for item in hits:
                # 解析 sold_at 为可读日期
                sold_at_raw = item.get("sold_at", "")
                if sold_at_raw:
                    try:
                        sold_date = pd.to_datetime(sold_at_raw).strftime("%Y-%m-%d")
                    except Exception:
                        sold_date = sold_at_raw
                else:
                    sold_date = ""

                results.append({
                    "keyword": keyword,
                    "listing_id": item.get("id"),
                    "title": item.get("title", ""),
                    "sold_price": item.get("sold_price"),
                    "sold_date": sold_date,
                    "sold_at": sold_at_raw,
                    "condition": item.get("condition", ""),
                    "followers": item.get("followerno", 0),
                    "category": item.get("category", ""),
                    "created_at": item.get("created_at", ""),
                    "fetch_date": datetime.today().strftime("%Y-%m-%d"),
                })

            print(f"  Page {page + 1}: +{len(hits)} records (total: {len(results)})")
            time.sleep(SLEEP_PER_PAGE)

        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] page {page}: {e}")
            time.sleep(SLEEP_PER_PAGE * 2)
            break

    return results


def run():
    keywords = load_top_keywords(TOP_N)
    all_records = []

    print(f"\nScraping {LOOKBACK_DAYS}-day historical sold data...\n")

    for i, kw in enumerate(keywords, 1):
        print(f"[{i}/{len(keywords)}] {kw}")
        records = fetch_historical_sold(kw)
        all_records.extend(records)
        print(f"  => {len(records)} records collected\n")

        if i < len(keywords):
            time.sleep(SLEEP_PER_KW)

    # 保存（去重 by listing_id，增量追加）
    df = pd.DataFrame(all_records)
    out_path = os.path.join(BASE_DIR, "historical_sold.csv")

    if os.path.exists(out_path):
        existing = pd.read_csv(out_path)
        df = pd.concat([existing, df]).drop_duplicates(subset="listing_id", keep="last")
        print(f"Merged with existing data: {len(existing)} old + {len(all_records)} new")

    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\nDone! Saved {len(df)} records to historical_sold.csv")
    print(f"Date range: {df['sold_date'].min()} ~ {df['sold_date'].max()}")

    # 每个关键词的统计
    print("\n===== Summary =====")
    for kw in keywords:
        subset = df[df["keyword"] == kw]
        if subset.empty:
            print(f"  {kw:<40} 0 records")
        else:
            print(
                f"  {kw:<40} {len(subset):>4} records  "
                f"${subset['sold_price'].median():>7.0f} median  "
                f"{subset['sold_date'].min()} ~ {subset['sold_date'].max()}"
            )


if __name__ == "__main__":
    run()
