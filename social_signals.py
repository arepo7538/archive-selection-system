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
from typing import Optional
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


# ══════════════════════════════════════════════════════════════════════════════
# 明星催化剂信号（Celebrity Buzz）
# ══════════════════════════════════════════════════════════════════════════════

def fetch_google_news_rss(keyword: str, max_results: int = 5) -> list[dict]:
    """
    Google News RSS 爬取，无需 API key
    搜索词：{keyword} celebrity worn spotted fashion
    返回: [{"title": ..., "link": ..., "published": ...}]
    """
    import urllib.parse
    import urllib.request
    from xml.etree import ElementTree

    query = urllib.parse.quote(f"{keyword} celebrity worn spotted fashion")
    url   = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            tree = ElementTree.parse(r)
        items = tree.findall(".//item")[:max_results]
        return [
            {
                "title":     i.findtext("title",   ""),
                "link":      i.findtext("link",    ""),
                "published": i.findtext("pubDate", ""),
            }
            for i in items
        ]
    except Exception as e:
        print(f"[Google News RSS] 报错: {e}")
        return []


def _extract_celebrity_names(headlines: list, client) -> Optional[str]:
    """
    用 DeepSeek 从新闻标题里提取穿戴该品牌的明星名字。
    只在 headlines 非空且传入了 llm_client 时调用；失败时静默返回 None。
    """
    if not headlines or client is None:
        return None
    try:
        titles = "\n".join(headlines)
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role":    "system",
                    "content": (
                        "从以下新闻标题中提取穿着该品牌/单品的明星名字。"
                        "只返回明星名字，多个用逗号分隔，没有则返回 None。"
                    ),
                },
                {"role": "user", "content": titles},
            ],
            max_tokens=50,
            temperature=0.1,
        )
        result = resp.choices[0].message.content.strip()
        return None if result.lower() == "none" else result
    except Exception as e:
        print(f"[Celebrity LLM] 提取报错: {e}")
        return None


def fetch_celebrity_buzz(keyword: str, llm_client=None) -> dict:
    """
    组合三路信号，检测是否有明星穿搭催化剂：
      1. Reddit  — r/streetwear + r/Grailed 关键词帖子数 & upvote
      2. Google Trends — 近4周热度 vs 历史均值比值（>1.2 视为异常上升）
      3. Google News RSS — 近期明星相关新闻标题

    返回:
      {
        "reddit_posts_1m":   int,
        "reddit_ups_1m":     int,
        "trends_ratio":      float,   # >1.2 = 近期热度高于历史均值
        "news_headlines":    list[str],
        "celebrity_mention": str | None,
        "buzz_level":        "high" | "medium" | "low" | "none",
        "fetch_date":        str,
      }
    """
    import datetime as _dt

    result: dict = {
        "reddit_posts_1m":   0,
        "reddit_ups_1m":     0,
        "trends_ratio":      1.0,
        "news_headlines":    [],
        "celebrity_mention": None,
        "buzz_level":        "none",
        "fetch_date":        _dt.date.today().isoformat(),
    }

    # ── 1. Reddit ──────────────────────────────────────────────────────────────
    try:
        celeb_query   = f"{keyword} celebrity OR worn OR spotted OR wearing"
        reddit_result = fetch_reddit_mentions(celeb_query, REDDIT_SUBREDDITS)
        result["reddit_posts_1m"] = reddit_result.get("reddit_posts_1m", 0)
        result["reddit_ups_1m"]   = reddit_result.get("reddit_ups_1m",   0)
    except Exception as e:
        print(f"[Celebrity Buzz] Reddit 报错: {e}")

    # ── 2. Google Trends ───────────────────────────────────────────────────────
    try:
        # 取前两词作为品牌粒度，避免过细
        parts = keyword.split()
        brand = " ".join(parts[:2]) if len(parts) > 1 else keyword
        df_trends = fetch_google_trends([brand], timeframe="today 1-m")
        if not df_trends.empty:
            result["trends_ratio"] = float(df_trends.iloc[0].get("trends_ratio", 1.0))
    except Exception as e:
        print(f"[Celebrity Buzz] Google Trends 报错: {e}")

    # ── 3. Google News RSS ─────────────────────────────────────────────────────
    try:
        news = fetch_google_news_rss(keyword)
        result["news_headlines"]    = [n["title"] for n in news[:3]]
        result["celebrity_mention"] = _extract_celebrity_names(
            result["news_headlines"], llm_client
        )
    except Exception as e:
        print(f"[Celebrity Buzz] Google News 报错: {e}")

    # ── 综合评分 → buzz_level ──────────────────────────────────────────────────
    score = 0
    if result["reddit_posts_1m"] >= 5:      score += 2
    elif result["reddit_posts_1m"] >= 2:    score += 1
    if result["trends_ratio"]     >= 1.5:   score += 2
    elif result["trends_ratio"]   >= 1.2:   score += 1
    if result["news_headlines"]:            score += 1
    if result["celebrity_mention"]:         score += 2

    result["buzz_level"] = (
        "high"   if score >= 4 else
        "medium" if score >= 2 else
        "low"    if score >= 1 else
        "none"
    )
    print(
        f"[Celebrity Buzz] '{keyword}' → buzz={result['buzz_level']} "
        f"(reddit={result['reddit_posts_1m']}, trends={result['trends_ratio']}, "
        f"news={len(result['news_headlines'])}, celeb={result['celebrity_mention']})"
    )
    return result
