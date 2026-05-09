"""
Grailed 数据采集模块
通过 Grailed 公开 Algolia 接口抓取在售 / 近30天已售商品
每周跑一次，增量追加
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta

KEYWORDS = [
    "Raf Simons consumed cargo pants",
    "Raf Simons consumed wide pants",
    "Raf Simons consumed tee",
    "Raf Simons FW02 knit sweater",
    "Helmut Lang bondage pants",
    "Helmut Lang FW00 sherpa",
    "Helmut Lang SS99",
    "Prada bowling shirt",
    "Vetements oversized hoodie",
    "Vetements DHL tee",
    # Hysteric Glamour
    "Hysteric Glamour snake jeans",
    "Hysteric Glamour varsity jacket",
    "Hysteric Glamour graphic tee",
    # Number (N)ine
    "Number Nine destroyed tee",
    "Number Nine AW03",
    "Number Nine AW09",
]

ALGOLIA_URL    = "https://mnrwefss2q-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_PARAMS = {
    "x-algolia-agent":        "Algolia for JavaScript (4.14.2); Browser (lite)",
    "x-algolia-api-key":      "c89dbaddf15fe70e1941a109bf7c2a3d",  # public_search_key from /api/config
    "x-algolia-application-id": "MNRWEFSS2Q",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

HITS_PER_PAGE = 40
MAX_PAGES     = 10   # 每个关键词最多抓 400 条样本（用于价格/收藏分析）


def _algolia_post(payload: dict) -> dict:
    resp = requests.post(ALGOLIA_URL, json=payload, headers=HEADERS,
                         params=ALGOLIA_PARAMS, timeout=12)
    resp.raise_for_status()
    return resp.json()["results"][0]


def fetch_grailed_listings(keyword: str) -> tuple[list[dict], int]:
    """
    抓取在售商品样本 + 返回 nbHits（全平台在售总数）
    nbHits 用于供需比分母，样本用于价格 / 收藏热度分析
    """
    results = []
    nb_hits = 0

    for page in range(MAX_PAGES):
        payload = {"requests": [{"indexName": "Listing_production",
                                  "params": f"query={keyword}&page={page}&hitsPerPage={HITS_PER_PAGE}"}]}
        try:
            result = _algolia_post(payload)
            if page == 0:
                nb_hits = result.get("nbHits", 0)
            hits = result.get("hits", [])
            if not hits:
                break
            today = datetime.today().strftime("%Y-%m-%d")
            for item in hits:
                results.append({
                    "keyword":    keyword,
                    "listing_id": item.get("id"),
                    "title":      item.get("title", ""),
                    "price_usd":  item.get("price_i") or item.get("price"),
                    "followers":  item.get("followerno", 0),
                    "category":   item.get("category", ""),
                    "condition":  item.get("condition", ""),
                    "created_at": item.get("created_at", ""),
                    "fetch_date": today,
                })
            time.sleep(0.8)
        except Exception as e:
            print(f"  [listings] page={page} 报错: {e}")
            break

    print(f"[在售] '{keyword}': 全平台总量={nb_hits:,}  抓取样本={len(results)}")
    return results, nb_hits


def fetch_grailed_sold_30d(keyword: str) -> tuple[list[dict], int]:
    """
    抓取近30天已售商品（用 sold_at_i 做时间戳过滤）
    返回样本列表 + nbHits（近30天全平台成交总数）
    """
    cutoff_ts = int((datetime.today() - timedelta(days=30)).timestamp())
    results   = []
    nb_hits   = 0

    for page in range(MAX_PAGES):
        params_str = (f"query={keyword}&page={page}&hitsPerPage={HITS_PER_PAGE}"
                      f"&numericFilters=sold_at_i%3E{cutoff_ts}")
        payload = {"requests": [{"indexName": "Listing_sold_production", "params": params_str}]}
        try:
            result = _algolia_post(payload)
            if page == 0:
                nb_hits = result.get("nbHits", 0)
            hits = result.get("hits", [])
            if not hits:
                break
            today = datetime.today().strftime("%Y-%m-%d")
            for item in hits:
                results.append({
                    "keyword":    keyword,
                    "listing_id": item.get("id"),
                    "title":      item.get("title", ""),
                    "price_usd":  item.get("price_i") or item.get("price"),
                    "sold_price": item.get("sold_price"),
                    "sold_at":    item.get("sold_at", ""),
                    "created_at": item.get("created_at", ""),
                    "fetch_date": today,
                })
            time.sleep(0.8)
        except Exception as e:
            print(f"  [sold] page={page} 报错: {e}")
            break

    print(f"[已售] '{keyword}': 近30天全平台成交={nb_hits:,}  抓取样本={len(results)}")
    return results, nb_hits


def run():
    all_listings, all_sold = [], []
    supply_totals, demand_totals = {}, {}

    for kw in KEYWORDS:
        print(f"\n── {kw} ──")
        listings, nb_supply = fetch_grailed_listings(kw)
        sold,     nb_demand = fetch_grailed_sold_30d(kw)

        supply_totals[kw] = nb_supply
        demand_totals[kw] = nb_demand

        all_listings.extend(listings)
        all_sold.extend(sold)
        time.sleep(2)

    # 保存全量总数（供 scorecard 直接使用，不受样本量影响）
    totals = pd.DataFrame([
        {"keyword": kw, "supply_total": supply_totals[kw], "demand_30d_total": demand_totals[kw],
         "fetch_date": datetime.today().strftime("%Y-%m-%d")}
        for kw in KEYWORDS
    ])
    try:
        existing = pd.read_csv("grailed_totals.csv")
        totals = pd.concat([existing, totals])
    except FileNotFoundError:
        pass
    totals.to_csv("grailed_totals.csv", index=False, encoding="utf-8-sig")

    # 样本数据（用于价格 / 收藏分析）
    df_listing = pd.DataFrame(all_listings)
    df_sold    = pd.DataFrame(all_sold)

    try:
        df_listing = pd.concat([pd.read_csv("grailed_listings.csv"), df_listing]).drop_duplicates("listing_id")
    except FileNotFoundError:
        pass
    try:
        df_sold = pd.concat([pd.read_csv("grailed_sold.csv"), df_sold]).drop_duplicates("listing_id")
    except FileNotFoundError:
        pass

    df_listing.to_csv("grailed_listings.csv", index=False, encoding="utf-8-sig")
    df_sold.to_csv("grailed_sold.csv",        index=False, encoding="utf-8-sig")

    print("\n✅ 数据已保存")
    print("\n===== 供需概览 =====")
    for kw in KEYWORDS:
        s, d = supply_totals[kw], demand_totals[kw]
        ratio = round(s / d, 2) if d else "∞"
        print(f"  {kw:<20} 在售={s:>6,}  近30天成交={d:>5,}  供需比={ratio}")


if __name__ == "__main__":
    run()
