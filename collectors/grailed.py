"""
Grailed 采集器 — 品牌级全量,不再依赖搜索词

与旧版 grailed_scraper.py 的本质区别
  · 取数主键是品牌:facetFilters=designers.name 精确过滤
    (实测 "Number (N)ine" 在售 13,742 条,旧文本搜索 "Number Nine AW03" 只能拿到 708)
  · Algolia 分页硬上限 1000 条/查询 → 用切片绕开:
      在售:category_path 一级切片,超限的品类内再按价格区间二分
      已售:sold_at_i 时间窗递归二分
    每个切片独享 1000 条配额,品牌全量可达
  · hitsPerPage=100(旧版 40)
  · requests.Session + urllib3.Retry 指数退避,出错重试而非静默断页

输出统一 schema 行(dict),由 run_collect.py 负责分类与入库。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ALGOLIA_URL = "https://mnrwefss2q-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_PARAMS = {
    "x-algolia-agent":          "Algolia for JavaScript (4.14.2); Browser (lite)",
    "x-algolia-api-key":        "c89dbaddf15fe70e1941a109bf7c2a3d",  # public search key
    "x-algolia-application-id": "MNRWEFSS2Q",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

INDEX_LISTINGS = "Listing_production"
INDEX_SOLD     = "Listing_sold_production"

HITS_PER_PAGE = 100
MAX_PAGES     = 10          # Algolia paginationLimitedTo=1000 → 10 页 × 100
PAGE_LIMIT    = HITS_PER_PAGE * MAX_PAGES
SLEEP         = 0.5         # 礼貌限速,秒/请求
PRICE_MAX     = 1_000_000   # 价格二分上界(美元)
MIN_SOLD_WINDOW = 3600      # 已售时间窗二分下界(秒)


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s


class _Stats:
    """单品牌单次采集的计数器(请求数/报错数),用于 pipeline_runs。"""
    def __init__(self):
        self.requests = 0
        self.errors = 0


def _post(s: requests.Session, stats: _Stats, index: str, params: dict) -> dict:
    """单次 Algolia 查询。params 为参数字典,这里负责编码。"""
    payload = {"requests": [{"indexName": index, "params": urlencode(params)}]}
    stats.requests += 1
    resp = s.post(ALGOLIA_URL, json=payload, params=ALGOLIA_PARAMS, timeout=15)
    resp.raise_for_status()
    time.sleep(SLEEP)
    return resp.json()["results"][0]


def _facet_filters(brand_facet: str, category: str | None = None) -> str:
    ff = [[f"designers.name:{brand_facet}"]]
    if category:
        ff.append([f"category_path:{category}"])
    return json.dumps(ff)


def verify_designer_facet(facet_name: str) -> dict:
    """验证 designers.name facet 精确名,返回平台在售总量。"""
    s = _session()
    stats = _Stats()
    r = _post(s, stats, INDEX_LISTINGS, {
        "query": "",
        "facetFilters": _facet_filters(facet_name),
        "hitsPerPage": 0,
        "page": 0,
    })
    nb = int(r.get("nbHits") or 0)
    return {"facet": facet_name, "nb_hits": nb, "valid": nb > 0}


# ════════════════════════════════════════════════════════════════
# 行映射:Algolia hit → 统一 schema
# ════════════════════════════════════════════════════════════════

def _iso(epoch) -> str | None:
    try:
        return datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def _listing_row(hit: dict, brand: str) -> dict:
    lid = str(hit.get("id"))
    return {
        "source":          "grailed",
        "listing_id":      lid,
        "brand":           brand,
        "title":           hit.get("title", ""),
        "category":        hit.get("category_path", ""),
        "condition":       hit.get("condition", ""),
        "size":            str(hit.get("size", "")),
        "seller_location": hit.get("location", ""),
        "currency":        "USD",
        "price_usd":       hit.get("price_i") or hit.get("price"),
        "hearts":          hit.get("followerno", 0),
        "heat_f":          hit.get("heat_f"),
        "url":             f"https://www.grailed.com/listings/{lid}",
        "created_at":      _iso(hit.get("created_at_i")),
    }


def _sold_row(hit: dict, brand: str) -> dict:
    lid = str(hit.get("id"))
    created, sold = hit.get("created_at_i"), hit.get("sold_at_i")
    days = round((sold - created) / 86400, 1) if created and sold else None
    return {
        "source":          "grailed",
        "listing_id":      lid,
        "brand":           brand,
        "title":           hit.get("title", ""),
        "category":        hit.get("category_path", ""),
        "condition":       hit.get("condition", ""),
        "size":            str(hit.get("size", "")),
        "seller_location": hit.get("location", ""),
        "sold_price_usd":  hit.get("sold_price"),
        "price_includes_shipping": int(bool(hit.get("sold_price_includes_shipping"))),
        "hearts":          hit.get("followerno", 0),
        "created_at":      _iso(created),
        "sold_at":         _iso(sold),
        "days_to_sell":    days,
        "fetch_date":      datetime.today().strftime("%Y-%m-%d"),
    }


# ════════════════════════════════════════════════════════════════
# 在售:facet 全量 + category/价格两级切片
# ════════════════════════════════════════════════════════════════

def _nb_hits(s, stats, index, base: dict) -> int:
    r = _post(s, stats, index, {**base, "hitsPerPage": 0})
    return r.get("nbHits", 0)


def _paginate(s, stats, index, base: dict, row_fn, out: dict) -> None:
    """翻页抓取一个切片(≤1000 条),结果按 listing_id 去重合入 out。"""
    for page in range(MAX_PAGES):
        try:
            r = _post(s, stats, index, {**base, "hitsPerPage": HITS_PER_PAGE, "page": page})
        except Exception as e:
            stats.errors += 1
            print(f"    ⚠️  翻页失败 page={page}: {e}")
            return
        hits = r.get("hits", [])
        for h in hits:
            row = row_fn(h)
            out[row["listing_id"]] = row
        if len(hits) < HITS_PER_PAGE:
            return


def _fetch_price_sliced(s, stats, base: dict, lo: int, hi: int, row_fn, out: dict) -> None:
    """价格区间 [lo, hi) 递归二分,每个叶子切片 ≤1000 条后翻页。"""
    numeric = json.dumps([f"price_i>={lo}", f"price_i<{hi}"])
    sliced = {**base, "numericFilters": numeric}
    n = _nb_hits(s, stats, INDEX_LISTINGS, sliced)
    if n == 0:
        return
    if n > PAGE_LIMIT and hi - lo > 1:
        mid = (lo + hi) // 2
        _fetch_price_sliced(s, stats, base, lo, mid, row_fn, out)
        _fetch_price_sliced(s, stats, base, mid, hi, row_fn, out)
    else:
        _paginate(s, stats, INDEX_LISTINGS, sliced, row_fn, out)


def fetch_brand_listings(cfg: dict, stats: _Stats | None = None) -> tuple[list[dict], int, _Stats]:
    """
    采集一个品牌的全量在售。
    返回 (rows, nb_total_平台总数, stats)。rows 已按 listing_id 去重。
    cfg 来自 watchlist.yaml:grailed_facet 必填,grailed_query 可选(超大品牌收窄)。
    """
    stats = stats or _Stats()
    s = _session()
    brand, facet = cfg["name"], cfg["grailed_facet"]
    query = cfg.get("grailed_query", "")

    base = {"query": query, "facetFilters": _facet_filters(facet)}
    row_fn = lambda h: _listing_row(h, brand)
    out: dict[str, dict] = {}

    total = _nb_hits(s, stats, INDEX_LISTINGS, base)
    print(f"  [{brand}] 在售总量 {total:,}", end="")

    if total <= PAGE_LIMIT:
        print(" — 直接翻页")
        _paginate(s, stats, INDEX_LISTINGS, base, row_fn, out)
    else:
        # 一级切片:category_path
        r = _post(s, stats, INDEX_LISTINGS,
                  {**base, "hitsPerPage": 0,
                   "facets": json.dumps(["category_path"]),
                   "maxValuesPerFacet": 100})
        cats = (r.get("facets") or {}).get("category_path", {})
        print(f" — 按 {len(cats)} 个品类切片")
        for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
            cat_base = {**base, "facetFilters": _facet_filters(facet, cat)}
            if cnt <= PAGE_LIMIT:
                _paginate(s, stats, INDEX_LISTINGS, cat_base, row_fn, out)
            else:
                # 二级切片:品类内价格二分
                _fetch_price_sliced(s, stats, cat_base, 0, PRICE_MAX, row_fn, out)

    coverage = len(out) / total * 100 if total else 100.0
    print(f"  [{brand}] 实际抓取 {len(out):,} 条(覆盖率 {coverage:.1f}%),"
          f"请求 {stats.requests} 次,报错 {stats.errors} 次")
    return list(out.values()), total, stats


# ════════════════════════════════════════════════════════════════
# 已售:sold_at_i 时间窗递归二分
# ════════════════════════════════════════════════════════════════

def _fetch_sold_window(s, stats, base: dict, t0: int, t1: int, row_fn, out: dict) -> None:
    numeric = json.dumps([f"sold_at_i>={t0}", f"sold_at_i<{t1}"])
    sliced = {**base, "numericFilters": numeric}
    n = _nb_hits(s, stats, INDEX_SOLD, sliced)
    if n == 0:
        return
    if n > PAGE_LIMIT and t1 - t0 > MIN_SOLD_WINDOW:
        mid = (t0 + t1) // 2
        _fetch_sold_window(s, stats, base, t0, mid, row_fn, out)
        _fetch_sold_window(s, stats, base, mid, t1, row_fn, out)
    else:
        _paginate(s, stats, INDEX_SOLD, sliced, row_fn, out)


def fetch_brand_sold(cfg: dict, days: int = 180,
                     stats: _Stats | None = None) -> tuple[list[dict], _Stats]:
    """采集一个品牌近 days 天的全量已售记录。"""
    stats = stats or _Stats()
    s = _session()
    brand, facet = cfg["name"], cfg["grailed_facet"]
    query = cfg.get("grailed_query", "")

    base = {"query": query, "facetFilters": _facet_filters(facet)}
    row_fn = lambda h: _sold_row(h, brand)
    out: dict[str, dict] = {}

    t1 = int(datetime.now().timestamp())
    t0 = int((datetime.now() - timedelta(days=days)).timestamp())
    _fetch_sold_window(s, stats, base, t0, t1, row_fn, out)

    print(f"  [{brand}] 近 {days} 天已售抓取 {len(out):,} 条,"
          f"请求 {stats.requests} 次,报错 {stats.errors} 次")
    return list(out.values()), stats


# ── 快速自测:python collectors/grailed.py "Number (N)ine" ──────────
if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "Number (N)ine"
    cfg = {"name": name, "grailed_facet": name}
    rows, total, st = fetch_brand_listings(cfg)
    print(f"\n样例 3 条:")
    for r in rows[:3]:
        print(f"  ${r['price_usd']:>6} | {r['hearts']:>4}❤ | {r['title'][:60]}")
