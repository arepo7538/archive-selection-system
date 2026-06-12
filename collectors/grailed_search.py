"""
Grailed 关键词即席搜索 — 供 AI agent 的任意关键词查询使用

与 collectors/grailed.py(品牌级全量采集)互补:
  · 采集管道按品牌 facet 全量入库(watchlist 品牌)
  · agent 面对用户输入的任意关键词(可能不在 watchlist),走文本搜索即时取数

返回结构与旧 grailed_scraper.py 保持一致(agent.py 依赖这些字段名)。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from collectors.grailed import (
    _session, _Stats, _post,
    INDEX_LISTINGS, INDEX_SOLD, HITS_PER_PAGE,
)

MAX_SEARCH_PAGES = 5   # 即席查询取样上限 500 条,够算均价/热度


def fetch_grailed_listings(keyword: str, max_pages: int = MAX_SEARCH_PAGES) -> tuple[list[dict], int]:
    """关键词在售搜索。返回 (样本行, 全平台 nbHits 总数)。"""
    s, stats = _session(), _Stats()
    results, nb_hits = [], 0
    today = datetime.today().strftime("%Y-%m-%d")

    for page in range(max_pages):
        try:
            r = _post(s, stats, INDEX_LISTINGS,
                      {"query": keyword, "hitsPerPage": HITS_PER_PAGE, "page": page})
        except Exception as e:
            print(f"  [grailed_search/listings] page={page} 报错: {e}")
            break
        if page == 0:
            nb_hits = r.get("nbHits", 0)
        hits = r.get("hits", [])
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
        if len(hits) < HITS_PER_PAGE:
            break

    return results, nb_hits


def fetch_grailed_sold_30d(keyword: str, max_pages: int = MAX_SEARCH_PAGES) -> tuple[list[dict], int]:
    """关键词近 30 天已售搜索。返回 (样本行, 全平台 nbHits 总数)。"""
    s, stats = _session(), _Stats()
    cutoff_ts = int((datetime.today() - timedelta(days=30)).timestamp())
    results, nb_hits = [], 0
    today = datetime.today().strftime("%Y-%m-%d")

    for page in range(max_pages):
        try:
            r = _post(s, stats, INDEX_SOLD,
                      {"query": keyword, "hitsPerPage": HITS_PER_PAGE, "page": page,
                       "numericFilters": f"sold_at_i>{cutoff_ts}"})
        except Exception as e:
            print(f"  [grailed_search/sold] page={page} 报错: {e}")
            break
        if page == 0:
            nb_hits = r.get("nbHits", 0)
        hits = r.get("hits", [])
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
        if len(hits) < HITS_PER_PAGE:
            break

    return results, nb_hits
