"""
社交媒体热度采集模块
数据源：
  1. Google Trends（pytrends）— 搜索热度趋势
  2. Reddit API — r/Grailed、r/streetwear 关键词讨论热度
每周跑一次
"""

import pandas as pd
import time
import random
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

# 时尚相关 subreddit allowlist —— 用于全站搜索后做后置过滤
# 小众品牌（Raf Simons / Helmut Lang）在固定 3 个 sub 命中率几乎为 0，
# 改成"全站搜索 + 时尚 sub 白名单过滤"才能拿到信号
FASHION_SUB_ALLOWLIST = {
    # 核心 fashion sub
    "grailed", "streetwear", "malefashionadvice", "femalefashionadvice",
    "japanesestreetwear", "rawdenim", "highfashion", "frugalmalefashion",
    "archivefashion", "fashion", "mensfashion", "womensfashion",
    "streetstyle", "redditfashion", "fashionhistory", "themetgala",
    "handbags", "sneakers",
    # 品牌专属 sub
    "rafsimons", "helmutlang", "balenciaga", "prada", "vetements", "yeezy",
    # 明星 / 流行文化（穿搭新闻常出现在这里）
    "fauxmoi", "popculturechat", "celebritygossip", "celebs",
    # 复刻（也讨论真品对比，做品牌热度判断有效）
    "designerreps", "fashionreps", "qualityrepsbst",
}


def fetch_wikipedia_pageviews(keyword: str, days: int = 90) -> dict:
    """
    Wikipedia Pageviews API —— 比 Google Trends 稳定得多的「话题热度」信号。

    云环境（Streamlit Cloud 共享 IP）调 pytrends 几乎必被 429 限流；
    Wikipedia REST API 不需要 key 也几乎不限流。
    返回与 Google Trends 同样 schema 的 dict，便于直接替换：

      {
        "source":           "wikipedia",
        "article":           匹配到的 Wikipedia 标题,
        "trends_recent_4w":  近 28 天日均访问量,
        "trends_historical": 全窗口日均访问量,
        "trends_ratio":      recent_4w / historical（>1.2 = 上升）,
        "daily":             [{date, views}, ...]  供绘图用,
      }

    失败时 ratio=None、daily=[]。404 时尝试常见后缀（_(brand), _(fashion_designer)）。
    """
    from datetime import datetime, timedelta

    end   = datetime.today()
    start = end - timedelta(days=days)
    candidates = [
        keyword.replace(" ", "_"),
        keyword.replace(" ", "_") + "_(brand)",
        keyword.replace(" ", "_") + "_(fashion_designer)",
        keyword.replace(" ", "_") + "_(fashion_brand)",
    ]
    headers = {"User-Agent": "luxury-resale-tracker/0.1 (research project)"}

    article_hit, items = None, []
    for art in candidates:
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia/all-access/all-agents/{art}/daily/"
            f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    article_hit = art
                    break
        except Exception as e:
            print(f"[Wikipedia] {art} 报错: {e}")

    if not items:
        print(f"[Wikipedia] '{keyword}' 未找到匹配条目")
        return {
            "source":            "wikipedia",
            "article":           None,
            "trends_recent_4w":  None,
            "trends_historical": None,
            "trends_ratio":      None,
            "daily":             [],
        }

    daily = [{"date": it["timestamp"][:8], "views": it.get("views", 0)} for it in items]
    views = [d["views"] for d in daily]
    recent  = sum(views[-28:]) / max(len(views[-28:]), 1)
    overall = sum(views) / max(len(views), 1)
    ratio   = round(recent / overall, 3) if overall > 0 else None

    print(
        f"[Wikipedia] '{keyword}' → '{article_hit}'  recent_4w={recent:.0f}  "
        f"baseline={overall:.0f}  ratio={ratio}"
    )
    return {
        "source":            "wikipedia",
        "article":           article_hit,
        "trends_recent_4w":  round(recent,  1),
        "trends_historical": round(overall, 1),
        "trends_ratio":      ratio,
        "daily":             daily,
    }


def _brand_root(keyword: str) -> str:
    """
    把"品牌 + 系列 + 款式"的细分关键词降到品牌粒度，用于 Reddit / News / Trends。
    例：'Raf Simons consumed tee' -> 'Raf Simons'
        'Vetements'              -> 'Vetements'
        'Number Nine AW03'       -> 'Number Nine'
    经验规则：保留前 2 个词；若首词全大写或长度 >= 6 视为完整品牌名，则只保留 1 词。
    """
    parts = keyword.strip().split()
    if not parts:
        return keyword
    if len(parts) == 1:
        return parts[0]
    return " ".join(parts[:2])


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
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                pytrends.build_payload(batch, timeframe=timeframe, geo="")
                df = pytrends.interest_over_time()
                if df.empty:
                    break

                for kw in batch:
                    if kw not in df.columns:
                        continue
                    series = df[kw]
                    # 近4周均值 vs 历史均值
                    recent_4w  = series.tail(4).mean()
                    historical = series.mean()
                    ratio      = round(recent_4w / historical, 3) if historical > 0 else 1.0

                    results.append({
                        "keyword":           kw,
                        "trends_recent_4w":  round(recent_4w, 2),
                        "trends_historical": round(historical, 2),
                        "trends_ratio":      ratio,   # >1 说明近期热度高于历史均值
                        "fetch_date":        datetime.today().strftime("%Y-%m-%d"),
                    })
                time.sleep(2)  # 避免 429
                break  # success — exit retry loop
            except Exception as e:
                err_str = str(e)
                is_429 = "429" in err_str or "Too Many Requests" in err_str
                if is_429 and attempt < max_retries:
                    wait = random.uniform(5, 10)
                    print(f"[Google Trends] 429 rate limit, retrying in {wait:.1f}s "
                          f"(attempt {attempt + 1}/{max_retries})…")
                    time.sleep(wait)
                else:
                    print(f"[Google Trends] batch={batch} 报错: {e}")
                    break

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


def fetch_reddit_mentions_global(keyword: str, limit: int = 50) -> dict:
    """
    Reddit 全站搜索 + 时尚 sub 白名单过滤。
    云端环境（Streamlit Cloud / 共享 IP）调 www.reddit.com 经常被 Cloudflare 拦截；
    old.reddit.com 对 bot 友好得多，先试 old，失败再退回 www。
    """
    params = {"q": keyword, "sort": "top", "limit": limit, "t": "month"}
    endpoints = [
        "https://old.reddit.com/search.json",
        "https://www.reddit.com/search.json",
    ]
    posts = []
    last_err = None
    request_ok = False
    for url in endpoints:
        try:
            resp = requests.get(url, headers=REDDIT_HEADERS, params=params, timeout=12)
            resp.raise_for_status()
            posts = resp.json()["data"]["children"]
            request_ok = True
            break
        except Exception as e:
            last_err = e
    # 只有「请求都失败」才算 fail；请求成功但 0 条结果是正常的（小众词、组合词）
    if not request_ok:
        print(f"[Reddit-global] keyword={keyword} 全部端点失败: {last_err}")

    total_posts, total_upvotes = 0, 0
    for p in posts:
        sub = p["data"].get("subreddit", "").lower()
        if sub in FASHION_SUB_ALLOWLIST:
            total_posts   += 1
            total_upvotes += p["data"].get("ups", 0)

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
    Google News RSS 爬取，无需 API key。
    查询策略：只用 keyword 作为搜索词（原先拼 'celebrity worn spotted fashion' 是 AND
    联结，词越多命中越少），抓回标题后再用关键词白名单做后置过滤，保留与明星/穿搭相关的条目。
    含 2 次重试 + 15s 超时，缓解偶发 SSL 握手超时。
    """
    import urllib.parse
    from xml.etree import ElementTree

    query = urllib.parse.quote(keyword)
    url   = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    # urllib 在 Python 3.9 + macOS 上经常报 "EOF occurred in violation of protocol"
    # （SSL/TLS 握手不稳定），改用 requests 走 OpenSSL，命中率明显提升
    root = None
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    if root is None:
        print(f"[Google News RSS] keyword={keyword} 重试 3 次仍失败: {last_err}")
        return []

    # 关键词白名单 —— 标题命中任一则视为"明星/穿搭"相关
    CELEB_TERMS = ("celebrity", "celebrities", "worn", "wearing", "wore",
                   "spotted", "stars", "rocked", "rocks", "outfit",
                   "look", "street style", "red carpet")

    items = root.findall(".//item")
    filtered = []
    for i in items:
        title = i.findtext("title", "") or ""
        if not any(t in title.lower() for t in CELEB_TERMS):
            continue
        filtered.append({
            "title":     title,
            "link":      i.findtext("link",    ""),
            "published": i.findtext("pubDate", ""),
        })
        if len(filtered) >= max_results:
            break
    return filtered


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

    # 三路信号都使用品牌粒度查询（'Raf Simons consumed tee' -> 'Raf Simons'），
    # 否则细分款在 Reddit / News 命中率几乎为 0
    brand = _brand_root(keyword)

    # ── 1. Reddit（全站搜索 + 时尚 sub 白名单过滤） ────────────────────────────
    try:
        reddit_result = fetch_reddit_mentions_global(brand, limit=50)
        result["reddit_posts_1m"] = reddit_result.get("reddit_posts_1m", 0)
        result["reddit_ups_1m"]   = reddit_result.get("reddit_ups_1m",   0)
    except Exception as e:
        print(f"[Celebrity Buzz] Reddit 报错: {e}")

    # ── 2. Topic Interest ──────────────────────────────────────────────────────
    # 主源：Wikipedia Pageviews（云环境稳定）
    # 备源：Google Trends（pytrends 在云端共享 IP 经常 429）
    try:
        wp = fetch_wikipedia_pageviews(brand, days=90)
        if wp.get("trends_ratio") is not None:
            result["trends_ratio"] = float(wp["trends_ratio"])
            result["topic_source"] = "wikipedia"
        else:
            df_trends = fetch_google_trends([brand], timeframe="today 1-m")
            if not df_trends.empty:
                result["trends_ratio"] = float(df_trends.iloc[0].get("trends_ratio", 1.0))
                result["topic_source"] = "google_trends"
    except Exception as e:
        print(f"[Celebrity Buzz] Topic Interest 报错: {e}")

    # ── 3. Google News RSS ─────────────────────────────────────────────────────
    try:
        news = fetch_google_news_rss(brand)
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
