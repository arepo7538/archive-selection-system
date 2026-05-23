"""
稀缺度评分卡核心模块
输入：grailed_listings.csv + grailed_sold.csv + grailed_totals.csv
输出：每个关键词4项指标 + 加权总分，保存至 scorecard.csv

4项指标：
  1. 供需比（越低越稀缺）     —— 用全平台 nbHits 总数计算
  2. 流通速度（越快越热门）    —— 近30天全平台成交总量
  3. 收藏热度（followers均值）
  4. 价格涨跌幅
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


WEIGHTS = {
    "supply_demand_score":  0.35,
    "velocity_score":       0.30,
    "grailed_hype_score":   0.25,
    "price_momentum_score": 0.10,
}


def _sep(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print('─'*55)


def min_max_scale(series: pd.Series, reverse: bool = False) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([5.0] * len(series), index=series.index)
    scaled = (series - mn) / (mx - mn) * 10
    return (10 - scaled) if reverse else scaled


# ================================================================
# 1. 供需比  —— 优先用全量 nbHits，没有则退回样本计数
# ================================================================
def calc_supply_demand(df_listing: pd.DataFrame, df_sold: pd.DataFrame) -> pd.DataFrame:
    _sep("① 供需比  =  全平台在售总数  ÷  近30天成交总数")

    try:
        totals = pd.read_csv("grailed_totals.csv")
        latest = totals.sort_values("fetch_date").groupby("keyword").last().reset_index()
        df = latest[["keyword", "supply_total", "demand_30d_total"]].copy()
        df.columns = ["keyword", "supply_count", "demand_count_30d"]
        df["demand_count_30d"] = df["demand_count_30d"].replace(0, 1)
        print("  数据来源: grailed_totals.csv（全平台真实总量）")
    except FileNotFoundError:
        print("  ⚠️  grailed_totals.csv 不存在，退回样本计数")
        supply = df_listing.groupby("keyword").size().reset_index(name="supply_count")
        cutoff = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        df_sold["fetch_date"] = pd.to_datetime(df_sold["fetch_date"])
        demand = df_sold[df_sold["fetch_date"] >= cutoff].groupby("keyword").size().reset_index(name="demand_count_30d")
        df = pd.merge(supply, demand, on="keyword", how="left").fillna({"demand_count_30d": 1})

    df["supply_demand_ratio"] = (df["supply_count"] / df["demand_count_30d"]).round(2)
    df["supply_demand_score"] = min_max_scale(df["supply_demand_ratio"], reverse=True)

    for _, row in df.iterrows():
        print(f"  {row['keyword']:<24} 在售={int(row['supply_count']):>5,}  "
              f"成交={int(row['demand_count_30d']):>4,}  "
              f"供需比={row['supply_demand_ratio']:>7.1f}  → 得分={row['supply_demand_score']:.2f}/10")

    return df[["keyword", "supply_count", "demand_count_30d", "supply_demand_ratio", "supply_demand_score"]]


# ================================================================
# 2. 流通速度
# ================================================================
def calc_velocity(df_sold: pd.DataFrame) -> pd.DataFrame:
    _sep("② 流通速度  =  近30天成交总量归一化（越大越热门）")

    try:
        totals = pd.read_csv("grailed_totals.csv")
        latest = totals.sort_values("fetch_date").groupby("keyword").last().reset_index()
        vel = latest[["keyword", "demand_30d_total"]].copy()
        vel.columns = ["keyword", "velocity_30d"]
        print("  数据来源: grailed_totals.csv 的 demand_30d_total")
    except FileNotFoundError:
        cutoff = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        df_sold["fetch_date"] = pd.to_datetime(df_sold["fetch_date"])
        vel = df_sold[df_sold["fetch_date"] >= cutoff].groupby("keyword").size().reset_index(name="velocity_30d")

    vel["velocity_score"] = min_max_scale(vel["velocity_30d"])

    max_v = vel["velocity_30d"].max()
    min_v = vel["velocity_30d"].min()
    print(f"  归一化公式: score = (成交量 - {min_v}) / ({max_v} - {min_v}) × 10")
    for _, row in vel.iterrows():
        print(f"  {row['keyword']:<24} 近30天成交={int(row['velocity_30d']):>4,}  → 得分={row['velocity_score']:.2f}/10")

    return vel


# ================================================================
# 3. 收藏热度
# ================================================================
def calc_grailed_hype(df_listing: pd.DataFrame) -> pd.DataFrame:
    _sep("③ 收藏热度  =  样本商品 followers 均值")

    hype = df_listing.groupby("keyword")["followers"].mean().reset_index(name="avg_followers")
    hype["grailed_hype_score"] = min_max_scale(hype["avg_followers"])

    for _, row in hype.iterrows():
        print(f"  {row['keyword']:<24} avg_followers={row['avg_followers']:.1f}  → 得分={row['grailed_hype_score']:.2f}/10")
    return hype


# ================================================================
# 4. 价格涨跌幅
# ================================================================
def calc_price_momentum(df_listing: pd.DataFrame) -> pd.DataFrame:
    _sep("④ 价格动量  =  (近4周均价 − 前4周均价) / 前4周均价")

    df_listing["fetch_date"] = pd.to_datetime(df_listing["fetch_date"])
    now    = datetime.today()
    recent = df_listing[df_listing["fetch_date"] >= now - timedelta(days=28)]
    prior  = df_listing[(df_listing["fetch_date"] >= now - timedelta(days=56)) &
                        (df_listing["fetch_date"] <  now - timedelta(days=28))]

    r_avg = recent.groupby("keyword")["price_usd"].median().reset_index(name="price_recent")
    p_avg = prior.groupby("keyword")["price_usd"].median().reset_index(name="price_prior")
    df = pd.merge(r_avg, p_avg, on="keyword", how="left")
    df["price_momentum"] = (df["price_recent"] - df["price_prior"]) / df["price_prior"].replace(0, np.nan)
    df["price_momentum_score"] = min_max_scale(df["price_momentum"].fillna(0))

    for _, row in df.iterrows():
        if pd.isna(row.get("price_prior")):
            note = "（前4周无数据，动量=0）"
        else:
            pct = row["price_momentum"] * 100
            note = f"近4周=${row['price_recent']:.0f}  前4周=${row['price_prior']:.0f}  涨幅={pct:+.1f}%"
        print(f"  {row['keyword']:<24} {note}  → 得分={row['price_momentum_score']:.2f}/10")

    return df[["keyword", "price_recent", "price_prior", "price_momentum", "price_momentum_score"]]


# ================================================================
# 汇总
# ================================================================
def build_scorecard():
    df_listing = pd.read_csv("grailed_listings.csv")
    df_sold    = pd.read_csv("grailed_sold.csv")

    sd   = calc_supply_demand(df_listing, df_sold)
    vel  = calc_velocity(df_sold)
    hype = calc_grailed_hype(df_listing)
    mom  = calc_price_momentum(df_listing)

    df = sd
    for sub in [vel, hype, mom]:
        df = pd.merge(df, sub, on="keyword", how="left")

    score_cols = list(WEIGHTS.keys())
    for col in score_cols:
        if col not in df.columns:
            df[col] = 5.0
        # 关键 keyword 如果在某子指标下数据缺失（如 listings 为空 → avg_followers NaN），
        # 这里用中性 5.0 兜底；否则 NaN 会传染到 total_score
        df[col] = df[col].fillna(5.0)

    _sep("⑤ 加权总分")
    print(f"  权重配置: { {k: v for k, v in WEIGHTS.items()} }")
    df["total_score"] = sum(df[col] * w for col, w in WEIGHTS.items())
    df["total_score"] = df["total_score"].round(2)
    df["rank"]        = df["total_score"].rank(ascending=False, na_option="bottom").fillna(len(df)).astype(int)
    df["calc_date"]   = datetime.today().strftime("%Y-%m-%d")

    for _, row in df.sort_values("total_score", ascending=False).iterrows():
        parts = "  +  ".join(f"{col.replace('_score','')}×{WEIGHTS[col]}={row[col]*WEIGHTS[col]:.3f}"
                              for col in score_cols)
        print(f"\n  [{row['rank']}] {row['keyword']}")
        print(f"      {parts}")
        print(f"      ──→ 总分 = {row['total_score']}")

    df_sorted = df.sort_values("total_score", ascending=False)
    df_sorted.to_csv("scorecard.csv", index=False, encoding="utf-8-sig")

    print(f"\n\n{'═'*55}")
    print("  最终稀缺度排行榜")
    print(f"{'═'*55}")
    print(df_sorted[["rank", "keyword", "total_score",
                      "supply_demand_ratio", "velocity_30d", "avg_followers"]].to_string(index=False))
    print("\n✅ scorecard.csv 已保存")
    return df_sorted


if __name__ == "__main__":
    build_scorecard()
