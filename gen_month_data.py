"""
生成横跨一个月的模拟数据（4次周快照），用于测试评分卡计算逻辑
数据参数基于各品牌真实市场量级估算
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

today = datetime.today()

# 每个品牌的市场参数（模拟真实量级）
BRAND_PARAMS = {
    "Balenciaga": {
        "listings_per_week": 180,   # 每周在售数量
        "sold_per_week":     55,    # 每周成交数量
        "price_range":       (180, 1200),
        "price_trend":       0.03,  # 每周涨幅
        "followers_range":   (2, 80),
    },
    "Vetements": {
        "listings_per_week": 90,
        "sold_per_week":     20,
        "price_range":       (120, 900),
        "price_trend":       -0.01,
        "followers_range":   (1, 40),
    },
    "Yeezy": {
        "listings_per_week": 250,
        "sold_per_week":     110,
        "price_range":       (80, 600),
        "price_trend":       0.05,
        "followers_range":   (5, 150),
    },
    "Prada Raf Simons": {
        "listings_per_week": 40,
        "sold_per_week":     8,
        "price_range":       (300, 2500),
        "price_trend":       0.02,
        "followers_range":   (1, 30),
    },
}

# 4次周快照日期（模拟过去一个月的每周采集）
SNAPSHOT_DATES = [today - timedelta(weeks=w) for w in range(3, -1, -1)]

all_listings = []
all_sold = []
listing_id_counter = 0
sold_id_counter = 0

for kw, params in BRAND_PARAMS.items():
    base_price = np.mean(params["price_range"])
    for week_idx, snap_date in enumerate(SNAPSHOT_DATES):
        date_str = snap_date.strftime("%Y-%m-%d")
        # 价格随时间漂移
        price_multiplier = 1 + params["price_trend"] * week_idx

        # 在售商品
        n = params["listings_per_week"] + np.random.randint(-20, 20)
        for _ in range(n):
            lo, hi = params["price_range"]
            price = np.random.uniform(lo * price_multiplier, hi * price_multiplier)
            fl_lo, fl_hi = params["followers_range"]
            all_listings.append({
                "keyword":    kw,
                "listing_id": f"L{listing_id_counter:05d}",
                "title":      f"{kw} listing {listing_id_counter}",
                "price_usd":  round(price, 0),
                "followers":  np.random.randint(fl_lo, fl_hi),
                "category":   np.random.choice(["tops", "bottoms", "footwear", "accessories"]),
                "condition":  np.random.choice(["is_new", "gently_used", "used", "worn"]),
                "sold":       False,
                "created_at": date_str,
                "fetch_date": date_str,
            })
            listing_id_counter += 1

        # 成交商品
        n_sold = params["sold_per_week"] + np.random.randint(-10, 10)
        for _ in range(n_sold):
            lo, hi = params["price_range"]
            price = np.random.uniform(lo * price_multiplier, hi * price_multiplier)
            all_sold.append({
                "keyword":    kw,
                "listing_id": f"S{sold_id_counter:05d}",
                "title":      f"{kw} sold {sold_id_counter}",
                "price_usd":  round(price, 0),
                "sold":       True,
                "created_at": date_str,
                "fetch_date": date_str,
            })
            sold_id_counter += 1

df_listings = pd.DataFrame(all_listings)
df_sold     = pd.DataFrame(all_sold)

df_listings.to_csv("grailed_listings.csv", index=False, encoding="utf-8-sig")
df_sold.to_csv("grailed_sold.csv",    index=False, encoding="utf-8-sig")

print("=== grailed_listings.csv ===")
print(df_listings.groupby("keyword").agg(
    总条数=("listing_id", "count"),
    日期跨度=("fetch_date", lambda x: f'{x.min()} ~ {x.max()}'),
    均价=("price_usd", lambda x: round(x.mean(), 0)),
).to_string())

print("\n=== grailed_sold.csv ===")
print(df_sold.groupby("keyword").agg(
    总条数=("listing_id", "count"),
    日期跨度=("fetch_date", lambda x: f'{x.min()} ~ {x.max()}'),
    均价=("price_usd", lambda x: round(x.mean(), 0)),
).to_string())

# 社媒数据（每周一条 Google Trends + Reddit）
social_rows = []
for kw, params in BRAND_PARAMS.items():
    for snap_date in SNAPSHOT_DATES:
        date_str = snap_date.strftime("%Y-%m-%d")
        social_rows.append({
            "keyword":           kw,
            "trends_recent_4w":  round(np.random.uniform(35, 85), 2),
            "trends_historical": round(np.random.uniform(30, 75), 2),
            "trends_ratio":      round(np.random.uniform(0.7, 1.6), 3),
            "reddit_posts_1m":   np.random.randint(1, 30),
            "reddit_ups_1m":     np.random.randint(20, 800),
            "fetch_date":        date_str,
        })

df_social = pd.DataFrame(social_rows)
df_social.to_csv("social_signals.csv", index=False, encoding="utf-8-sig")

print("\n=== social_signals.csv ===")
print(df_social.groupby("keyword").agg(
    快照次数=("fetch_date", "count"),
    最新trends_ratio=("trends_ratio", "last"),
    最新reddit_ups=("reddit_ups_1m", "last"),
).to_string())
