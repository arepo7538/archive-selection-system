"""
Discovery 模块：无预设品牌，让数据自己发现 designer/luxury 热门单品
- 按 followerno 降序抓取 grailed/hype 品类前500条
- 输出 Top10 品牌热度榜 + Top20 高频单品词组榜
"""

import re
import requests
import pandas as pd
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

    # 保存
    today = datetime.today().strftime("%Y-%m-%d")
    df_brands["table"]     = "brand_ranking"
    df_brands["fetch_date"] = today
    df_bigrams["table"]    = "bigram_ranking"
    df_bigrams["fetch_date"] = today

    out = pd.concat([df_brands, df_bigrams], ignore_index=True)
    out.to_csv("discovery.csv", index=False, encoding="utf-8-sig")
    print("\n✅ 结果已保存至 discovery.csv")
    return df_brands, df_bigrams


if __name__ == "__main__":
    run()
