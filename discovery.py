"""
Discovery 模块：无预设品牌，让数据自己发现 designer/luxury 热门单品
- 按 followerno 降序抓取 grailed/hype 品类前500条
- 输出 Top10 品牌热度榜 + Top20 高频单品词组榜
- --suggest:对比 watchlist,提名未跟踪的高热品牌
"""

from __future__ import annotations

import argparse
import re
import requests
import pandas as pd
import yaml
from collections import Counter, defaultdict
from datetime import datetime

# ── Algolia 配置（与 grailed_scraper.py 保持一致）──
ALGOLIA_URL    = "https://mnrwefss2q-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_PARAMS = {
    "x-algolia-agent":           "Algolia for JavaScript (4.14.2); Browser (lite)",
    "x-algolia-api-key":         "c89dbaddf15fe70e1941a109bf7c2a3d",
    "x-algolia-application-id":  "MNRWEFSS2Q",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

TARGET_TOTAL  = 500
HITS_PER_PAGE = 100   # 每页最多100条，5页凑足500

# ── 无意义词过滤表 ──
STOPWORDS = {
    "the","a","an","and","or","of","in","on","at","to","for","with",
    "de","le","la","los","les","el","by","from","is","it","its",
    "size","fit","fits","xl","xxl","xs","sm","med","lg","new","vintage",
    "rare","archive","ss","fw","aw","sp","re","us","eu","uk","jp",
    "mens","men","womens","women","unisex","one","two","three","four",
    "item","piece","set","lot","pair","used","sold","sale","free",
    "shipping","offer","make","price","drop","tag","tagged","obo",
    "condition","excellent","great","good","wear","worn","deadstock",
    "nwt","nwot","ds","vnds","fair","poor","play","not","no","w",
    "o","s","m","l","p","n",
}


def fetch_top_listings(total: int = TARGET_TOTAL) -> list[dict]:
    """按 followerno 降序抓取 grailed+hype 品类在售前 total 条"""
    results = []
    pages_needed = -(-total // HITS_PER_PAGE)   # ceil div

    for page in range(pages_needed):
        params_str = (
            f"query=&page={page}&hitsPerPage={HITS_PER_PAGE}"
            f"&filters=strata%3Agrailed%20OR%20strata%3Ahype"
        )
        payload = {"requests": [{
            "indexName": "Listing_by_followers_production",
            "params": params_str,
        }]}
        try:
            resp = requests.post(ALGOLIA_URL, json=payload,
                                 headers=HEADERS, params=ALGOLIA_PARAMS, timeout=15)
            resp.raise_for_status()
            data = resp.json()["results"][0]
            hits = data.get("hits", [])
            if not hits:
                print(f"  第{page}页无数据，提前退出")
                break
            for h in hits:
                designers = h.get("designer_names") or []
                if isinstance(designers, str):
                    designers = [designers]
                results.append({
                    "listing_id":     h.get("id"),
                    "title":          h.get("title", ""),
                    "designer_names": designers,
                    "price_usd":      h.get("price_i") or h.get("price"),
                    "followerno":     h.get("followerno", 0),
                    "category":       h.get("category", ""),
                    "strata":         h.get("strata", ""),
                })
            print(f"  第{page+1}/{pages_needed}页：抓到{len(hits)}条，累计{len(results)}条")
        except Exception as e:
            print(f"  第{page}页报错: {e}")
            break

    return results[:total]


def brand_ranking(records: list[dict], top_n: int = 10) -> pd.DataFrame:
    """统计品牌出现频次 + 平均 followerno"""
    brand_follows: dict[str, list[int]] = defaultdict(list)
    for r in records:
        for brand in r["designer_names"]:
            b = brand.strip()
            if b:
                brand_follows[b].append(r["followerno"])

    rows = []
    for brand, follows in brand_follows.items():
        rows.append({
            "brand":           brand,
            "listing_count":   len(follows),
            "avg_followerno":  round(sum(follows) / len(follows), 1),
            "total_followerno": sum(follows),
        })

    df = (pd.DataFrame(rows)
            .sort_values("listing_count", ascending=False)
            .head(top_n)
            .reset_index(drop=True))
    df.index += 1
    return df


def _tokenize(title: str) -> list[str]:
    tokens = re.sub(r"[^a-zA-Z0-9\s]", " ", title.lower()).split()
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def bigram_ranking(records: list[dict], top_n: int = 20) -> pd.DataFrame:
    """对 title 做 bigram 词频统计，附带品牌、followerno、价格"""
    bigram_data: dict[str, list] = defaultdict(list)   # bigram → list of records

    for r in records:
        tokens = _tokenize(r["title"])
        bigrams = set()
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]} {tokens[i+1]}"
            bigrams.add(bg)
        for bg in bigrams:
            bigram_data[bg].append(r)

    rows = []
    for bg, items in bigram_data.items():
        brands = Counter()
        for it in items:
            for b in it["designer_names"]:
                if b.strip():
                    brands[b.strip()] += 1
        top_brand = brands.most_common(1)[0][0] if brands else "—"
        prices = [it["price_usd"] for it in items if it["price_usd"]]
        rows.append({
            "bigram":          bg,
            "count":           len(items),
            "top_brand":       top_brand,
            "avg_followerno":  round(sum(it["followerno"] for it in items) / len(items), 1),
            "median_price_usd": round(pd.Series(prices).median(), 0) if prices else None,
        })

    df = (pd.DataFrame(rows)
            .sort_values("count", ascending=False)
            .head(top_n)
            .reset_index(drop=True))
    df.index += 1
    return df


def run():
    print("=" * 60)
    print("  Discovery：无预设品牌的热门单品发现")
    print("=" * 60)

    print(f"\n[Step 1] 按 followerno 降序抓取 grailed/hype 前{TARGET_TOTAL}条...")
    records = fetch_top_listings(TARGET_TOTAL)
    print(f"  实际获取 {len(records)} 条")

    print("\n[Step 2] 品牌热度排行（Top10）")
    print("─" * 60)
    df_brands = brand_ranking(records, top_n=10)
    print(df_brands.to_string())

    print("\n[Step 3] 高频单品词组排行（Top20）")
    print("─" * 60)
    df_bigrams = bigram_ranking(records, top_n=20)
    print(df_bigrams.to_string())

    # 保存汇总排行
    today = datetime.today().strftime("%Y-%m-%d")
    df_brands["table"]      = "brand_ranking"
    df_brands["fetch_date"] = today
    df_bigrams["table"]     = "bigram_ranking"
    df_bigrams["fetch_date"] = today

    import os as _os
    _os.makedirs("data", exist_ok=True)
    out = pd.concat([df_brands, df_bigrams], ignore_index=True)
    out.to_csv("data/discovery.csv", index=False, encoding="utf-8-sig")
    print("\n✅ 结果已保存至 data/discovery.csv")

    # 保存500条原始数据
    df_raw = pd.DataFrame(records)
    df_raw["fetch_date"] = today
    # designer_names 是 list，转成逗号分隔字符串方便存 CSV
    df_raw["designer_names"] = df_raw["designer_names"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else str(x)
    )
    df_raw.to_csv("data/discovery_raw.csv", index=False, encoding="utf-8-sig")
    print(f"✅ {len(df_raw)} 条原始数据已保存至 data/discovery_raw.csv")

    # ── 品牌池漏斗 L1:热度时间序列入库(brand_heat)──────────
    try:
        from lib import db as _db
        from collections import defaultdict as _dd
        prices = _dd(list)
        for r in records:
            for b in r["designer_names"]:
                if b.strip() and r.get("price_usd"):
                    prices[b.strip()].append(r["price_usd"])
        conn = _db.connect()
        for _, row in df_brands.iterrows():
            b = str(row["brand"])
            med = float(pd.Series(prices[b]).median()) if prices[b] else None
            conn.execute(
                """INSERT OR REPLACE INTO brand_heat
                   (brand, scan_date, source, listing_count, avg_hearts, median_price)
                   VALUES (?,?,'discovery',?,?,?)""",
                (b, today, int(row["listing_count"]),
                 float(row["avg_followerno"]), med),
            )
        conn.commit()
        conn.close()
        print(f"✅ {len(df_brands)} 个品牌热度已写入 brand_heat 表")
    except Exception as e:
        print(f"⚠️  brand_heat 入库失败(不影响 CSV):{e}")

    return df_brands, df_bigrams


def get_candidate_keywords(top_n: int = 5, min_count: int = 3) -> list[str]:
    """
    从上次 discovery 结果读取高热度新品牌，作为候选关键词返回。
    自动跳过已被现有 KEYWORDS 覆盖的品牌。

    参数
    ----
    top_n     : 最多返回几个新品牌（默认5个）
    min_count : 品牌在500条中出现次数的最低门槛（默认3次）

    返回
    ----
    list[str]  — 例如 ["Rick Owens", "Chrome Hearts", "Maison Margiela"]
    """
    try:
        df = pd.read_csv("data/discovery.csv")
    except FileNotFoundError:
        print("  [discovery] data/discovery.csv 不存在，跳过候选词注入（先运行 python discovery.py）")
        return []

    brand_df = (
        df[df["table"] == "brand_ranking"]
        .dropna(subset=["brand", "listing_count"])
        .copy()
    )
    brand_df["listing_count"] = brand_df["listing_count"].astype(int)
    brand_df = brand_df[brand_df["listing_count"] >= min_count].sort_values(
        "listing_count", ascending=False
    )

    # 读取现有关键词列表，用于去重
    try:
        from grailed_scraper import KEYWORDS as _existing_kws
        existing_lower = [kw.lower() for kw in _existing_kws]
    except ImportError:
        existing_lower = []

    candidates: list[str] = []
    for _, row in brand_df.iterrows():
        brand = str(row["brand"]).strip()
        if not brand:
            continue
        # 如果品牌名已是现有任一关键词的子串，则跳过（已覆盖）
        already_covered = any(brand.lower() in kw for kw in existing_lower)
        if not already_covered:
            candidates.append(brand)
        if len(candidates) >= top_n:
            break

    return candidates


def _load_watchlist_brands(path: str = "watchlist.yaml") -> set[str]:
    with open(path, encoding="utf-8") as f:
        brands = yaml.safe_load(f)["brands"]
    tracked = set()
    for b in brands:
        tracked.add(b["name"].lower())
        tracked.add(b.get("grailed_facet", b["name"]).lower())
    return tracked


def _suggest_yaml_entry(brand: str, facet: str, nb_hits: int) -> str:
    token = brand.split()[0].lower() if brand.split() else brand.lower()
    return (
        f'  - name: "{brand}"\n'
        f'    grailed_facet: "{facet}"\n'
        f'    title_tokens: ["{token}"]\n'
        f'    yahoo_query: ""\n'
        f'    series: {{}}\n'
        f'    # facet 验证: {nb_hits:,} 条在售'
    )


def suggest_watchlist(top_n: int = 5, min_count: int = 3) -> None:
    """对比 watchlist,打印未跟踪高热品牌 TopN + 可复制 yaml 条目。"""
    from collectors.grailed import verify_designer_facet

    print("=" * 60)
    print("  Watchlist 品牌提名 (--suggest)")
    print("=" * 60)

    tracked = _load_watchlist_brands()
    print(f"\n当前 watchlist 跟踪 {len(tracked)} 个品牌名/facet\n")

    print(f"抓取 grailed/hype Top{TARGET_TOTAL} 按 followerno 排序...")
    records = fetch_top_listings(TARGET_TOTAL)
    df_brands = brand_ranking(records, top_n=50)
    df_brands = df_brands[df_brands["listing_count"] >= min_count]

    untracked = []
    for _, row in df_brands.iterrows():
        brand = str(row["brand"]).strip()
        if brand.lower() in tracked:
            continue
        untracked.append(row)
        if len(untracked) >= top_n:
            break

    if not untracked:
        print("未发现 watchlist 外的高热品牌(或均已跟踪)。")
        return

    print(f"\n未跟踪的高热品牌 Top{len(untracked)}:\n")
    for i, row in enumerate(untracked, 1):
        brand = str(row["brand"])
        print(f"  [{i}] {brand} — 出现 {int(row['listing_count'])} 次, "
              f"avg followerno {row['avg_followerno']}")

    print("\n" + "─" * 60)
    print("建议 watchlist.yaml 条目(facet 已验证,可直接复制):\n")
    for row in untracked:
        brand = str(row["brand"])
        check = verify_designer_facet(brand)
        if check["valid"]:
            facet = check["facet"]
            nb = check["nb_hits"]
            status = "✅"
        else:
            facet = brand
            nb = 0
            status = "⚠️ facet 未命中,请手动核对 Grailed designers.name"
        print(f"# {status}")
        print(_suggest_yaml_entry(brand, facet, nb))
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Archive 热门品牌/单品发现")
    ap.add_argument(
        "--suggest",
        action="store_true",
        help="对比 watchlist,提名未跟踪的高热品牌(含 facet 验证)",
    )
    args = ap.parse_args()
    if args.suggest:
        suggest_watchlist()
    else:
        run()
