"""
社交媒体热度采集模块
数据源：
  1. Google Trends（pytrends）— 搜索热度趋势
  2. Reddit API — r/Grailed、r/streetwear 关键词讨论热度
每周跑一次
"""

import pandas as pd
import time
import requests
from datetime import datetime
from pytrends.request import TrendReq


# ---- 配置区 ----
KEYWORDS = [
    "Balenciaga",
    "Vetements",
    "Yeezy",
    "Prada Raf Simons",
]

REDDIT_SUBREDDITS = ["Grailed", "streetwear", "malefashionadvice"]
REDDIT_HEADERS = {
    "User-Agent": "luxury-resale-tracker/0.1 (research project)"
}


# ================================================================
# 1. Google Trends
# ================================================================
def fetch_google_trends(keywords: list[str], timeframe: str = "today 3-m") -> pd.DataFrame:
    """
    获取过去3个月的 Google 搜索热度
    返回每个关键词的：当前均值、历史基线、热度比值
    timeframe 可选: 'today 1-m', 'today 3-m', 'today 12-m'
    """
    pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
    results = []

    # Google Trends 每次最多5个关键词
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo="")
            df = pytrends.interest_over_time()
            if df.empty:
                continue

            for kw in batch:
                if kw not in df.columns:
                    continue
                series = df[kw]
                # 近4周均值 vs 历史均值
                recent_4w  = series.tail(4).mean()
                historical = series.mean()
                ratio      = round(recent_4w / historical, 3) if historical > 0 else 1.0

                results.append({
                    "keyword":          kw,
                    "trends_recent_4w": round(recent_4w, 2),
                    "trends_historical": round(historical, 2),
                    "trends_ratio":     ratio,   # >1 说明近期热度高于历史均值
                    "fetch_date":       datetime.today().strftime("%Y-%m-%d"),
                })
            time.sleep(2)  # 避免 429
        except Exception as e:
            print(f"[Google Trends] batch={batch} 报错: {e}")

    df_out = pd.DataFrame(results)
    print(f"[Google Trends] 采集完成，共 {len(df_out)} 条")
    return df_out


# ================================================================
# 2. Reddit 热度
# ================================================================
def fetch_reddit_mentions(keyword: str, subreddits: list[str], limit: int = 100) -> dict:
    """
    搜索关键词在指定 subreddit 中近期的帖子数和总 upvote 数
    使用 Reddit 公开 JSON 接口，不需要 API key
    """
    total_posts  = 0
    total_upvotes = 0

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {
            "q":        keyword,
            "restrict_sr": 1,
            "sort":     "new",
            "limit":    limit,
            "t":        "month",   # 近1个月
        }
        try:
            resp = requests.get(url, headers=REDDIT_HEADERS, params=params, timeout=10)
            resp.raise_for_status()
            posts = resp.json()["data"]["children"]
            total_posts   += len(posts)
            total_upvotes += sum(p["data"].get("ups", 0) for p in posts)
            time.sleep(1)
        except Exception as e:
            print(f"[Reddit] keyword={keyword} sub={sub} 报错: {e}")

    return {
        "keyword":         keyword,
        "reddit_posts_1m": total_posts,
        "reddit_ups_1m":   total_upvotes,
        "fetch_date":      datetime.today().strftime("%Y-%m-%d"),
    }


def fetch_all_reddit(keywords: list[str]) -> pd.DataFrame:
    results = []
    for kw in keywords:
        row = fetch_reddit_mentions(kw, REDDIT_SUBREDDITS)
        results.append(row)
        print(f"[Reddit] '{kw}' → posts={row['reddit_posts_1m']} ups={row['reddit_ups_1m']}")
        time.sleep(2)
    return pd.DataFrame(results)


# ================================================================
# 主流程
# ================================================================
def run():
    print("=== 采集 Google Trends ===")
    df_trends = fetch_google_trends(KEYWORDS)

    print("\n=== 采集 Reddit ===")
    df_reddit = fetch_all_reddit(KEYWORDS)

    # 合并（df_trends 可能为空，如 Google 限流时）
    if df_trends.empty:
        df_social = df_reddit.copy()
        df_social["trends_recent_4w"] = None
        df_social["trends_historical"] = None
        df_social["trends_ratio"] = None
    else:
        df_social = pd.merge(df_trends, df_reddit, on=["keyword", "fetch_date"], how="outer")

    # 追加写入
    try:
        existing = pd.read_csv("social_signals.csv")
        df_social = pd.concat([existing, df_social])
    except FileNotFoundError:
        pass

    df_social.to_csv("social_signals.csv", index=False, encoding="utf-8-sig")
    print("\n✅ 社媒数据已保存至 social_signals.csv")
    print(df_social.tail())


if __name__ == "__main__":
    run()
