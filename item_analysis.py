"""
单品下探分析模块
对每个季度关键词，从 listing title 提取高频 bigram 单品名，
计算出现次数、价格中位数、平均收藏数、粗略供需比
"""

import re
import pandas as pd
from collections import Counter

STOPWORDS = {
    "size", "black", "white", "grey", "gray", "blue", "red",
    "green", "navy", "s", "m", "l", "xl", "xxl", "fits", "good",
    "condition", "used", "vintage", "rare", "new", "item",
    "sold", "price", "shipping", "offer", "worn", "great",
    "authentic", "genuine", "real", "deadstock", "ds",
    "the", "a", "an", "in", "of", "for", "with", "and", "or",
    "nwt", "nwot", "fw", "ss", "aw", "sp", "sz", "tag", "tags",
    "please", "read", "see", "photos", "photo", "look",
    "listing", "lmk", "dm", "make", "will", "can", "have",
}

TOP_N = 10


def tokenize(title: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", title.lower())


def extract_bigrams(title: str) -> list[str]:
    words = tokenize(title)
    bigrams = []
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        if (w1 not in STOPWORDS and w2 not in STOPWORDS
                and len(w1) > 1 and len(w2) > 1):
            bigrams.append(f"{w1} {w2}")
    return bigrams


def analyze_keyword(df_kw: pd.DataFrame, demand_30d: float) -> pd.DataFrame:
    """
    对单个 keyword 的所有 listings 做 bigram 分析，返回 top-N 单品原始指标
    （不在此处打分，由 run() 全局归一化后统一打分）
    """
    all_bigrams = []
    for title in df_kw["title"].dropna():
        all_bigrams.extend(extract_bigrams(str(title)))

    if not all_bigrams:
        return pd.DataFrame()

    top_bigrams = [bg for bg, _ in Counter(all_bigrams).most_common(TOP_N)]

    rows = []
    for bg in top_bigrams:
        mask = df_kw["title"].str.lower().str.contains(
            re.escape(bg), na=False, regex=True
        )
        subset = df_kw[mask]
        count         = len(subset)
        median_price  = subset["price_usd"].median()
        avg_followers = subset["followers"].mean()

        estimated_demand = max(demand_30d / 10, 0.5)
        approx_ratio     = round(count / estimated_demand, 1)

        rows.append({
            "item_name":        bg,
            "count":            count,
            "median_price_usd": round(median_price, 0) if pd.notna(median_price) else None,
            "avg_followers":    round(avg_followers, 1) if pd.notna(avg_followers) else None,
            "approx_ratio":     approx_ratio,
        })

    return pd.DataFrame(rows)


def _global_scale(s: pd.Series, reverse: bool = False) -> pd.Series:
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series([5.0] * len(s), index=s.index)
    scaled = (s - mn) / (mx - mn) * 10
    return (10 - scaled) if reverse else scaled


def run():
    df_listings = pd.read_csv("grailed_listings.csv")

    try:
        totals = pd.read_csv("grailed_totals.csv")
        latest_totals = (totals.sort_values("fetch_date")
                               .groupby("keyword").last()
                               .reset_index()
                               [["keyword", "demand_30d_total"]])
    except FileNotFoundError:
        latest_totals = pd.DataFrame(columns=["keyword", "demand_30d_total"])

    # ── Step 1：收集所有季度的原始指标 ──
    all_rows = []
    for kw in df_listings["keyword"].unique():
        df_kw = df_listings[df_listings["keyword"] == kw].copy()
        demand_row = latest_totals[latest_totals["keyword"] == kw]
        demand_30d = float(demand_row["demand_30d_total"].values[0]) if len(demand_row) else 1.0

        df_items = analyze_keyword(df_kw, demand_30d)
        if df_items.empty:
            continue
        df_items.insert(0, "keyword", kw)
        all_rows.append(df_items)

    if not all_rows:
        print("⚠️  无有效数据")
        return

    # ── Step 2：全局归一化打分 ──
    df_all = pd.concat(all_rows, ignore_index=True)

    df_all["hype_score"]     = _global_scale(df_all["avg_followers"].fillna(0)).round(2)
    df_all["sd_score"]       = _global_scale(df_all["approx_ratio"].fillna(df_all["approx_ratio"].max()),
                                              reverse=True).round(2)
    df_all["momentum_score"] = 5.0

    df_all["item_score"] = (
        df_all["hype_score"]     * 0.40 +
        df_all["sd_score"]       * 0.40 +
        df_all["momentum_score"] * 0.20
    ).round(2)

    df_all = df_all.sort_values("item_score", ascending=False).reset_index(drop=True)
    df_all.insert(0, "global_rank", range(1, len(df_all) + 1))

    # ── Step 3：保存完整数据 ──
    df_all.to_csv("item_analysis.csv", index=False, encoding="utf-8-sig")

    # ── Step 4：打印全局 Top 20 ──
    print(f"\n{'═'*72}")
    print("  全局单品稀缺度排行榜  Top 20")
    print(f"{'═'*72}")
    print(f"  {'#':>3}  {'单品名':<24} {'季度':<22} {'中位价$':>7}  {'均收藏':>6}  {'粗供需比':>8}  {'item_score':>10}")
    print(f"  {'─'*68}")
    for _, row in df_all.head(20).iterrows():
        price_str = f"{int(row['median_price_usd'])}$" if pd.notna(row['median_price_usd']) else "N/A"
        foll_str  = f"{row['avg_followers']:.1f}"      if pd.notna(row['avg_followers'])    else "N/A"
        print(f"  {int(row['global_rank']):>3}  {row['item_name']:<24} {row['keyword']:<22} "
              f"{price_str:>7}  {foll_str:>6}  {row['approx_ratio']:>7.1f}x  {row['item_score']:>10.2f}")

    print(f"\n✅ 完整数据已保存至 item_analysis.csv（共 {len(df_all)} 条记录）")


if __name__ == "__main__":
    run()
