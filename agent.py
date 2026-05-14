"""
LangGraph Multi-Agent Workflow — Archive Fashion Market Analyzer
================================================================
三节点顺序流水线：
  fetch_data  →  score  →  analyze
每个节点对应一个工具函数，最终由 DeepSeek LLM 生成中文分析报告。

用法：
  python agent.py "Number Nine AW03"
  # 或在其他模块中：
  from agent import analyze_item
  report = analyze_item("Helmut Lang SS99")
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from typing import TypedDict, Optional
from datetime import datetime

# ── LangGraph ──────────────────────────────────────────────────────────────────
from langgraph.graph import StateGraph, END

# ── OpenAI-compatible client (DeepSeek) ───────────────────────────────────────
from openai import OpenAI

# ── Import scraper functions from existing module ─────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from grailed_scraper import fetch_grailed_listings, fetch_grailed_sold_30d


# ══════════════════════════════════════════════════════════════════════════════
# State
# ══════════════════════════════════════════════════════════════════════════════

class MarketAnalysisState(TypedDict):
    keyword: str
    original_keyword: str   # 中文输入或放宽前保留原词
    was_translated: bool    # 是否经过中文→英文翻译
    retry_count: int        # 关键词放宽重试次数（默认 0）
    keyword_relaxed: bool   # 是否触发过关键词放宽
    market_data: dict
    score_data: dict
    price_prediction: dict
    celebrity_data: dict          # 明星催化剂信号
    final_report: str
    messages: list


# ══════════════════════════════════════════════════════════════════════════════
# Tool 1 — fetch_market_data
# ══════════════════════════════════════════════════════════════════════════════

def fetch_market_data(keyword: str) -> dict:
    """
    调用 grailed_scraper.fetch_grailed_listings / fetch_grailed_sold_30d
    返回：在售总数、近30天成交量、均价/最高/最低价、平均收藏数

    注意：每次调用会对 Algolia API 发起最多 10×2 = 20 次请求（含 0.8s 间隔），
          预计耗时 30-60 秒，属正常。
    """
    print(f"[Tool 1] Fetching market data for: '{keyword}' …")

    try:
        listings, nb_supply = fetch_grailed_listings(keyword)
        sold,     nb_demand = fetch_grailed_sold_30d(keyword)
    except Exception as e:
        print(f"[Tool 1] API error: {e}")
        return {"error": str(e), "keyword": keyword, "supply_count": 0, "demand_count_30d": 0}

    prices      = [x["price_usd"]  for x in listings if x.get("price_usd")]
    sold_prices = [x["sold_price"] for x in sold     if x.get("sold_price")]
    followers   = [x["followers"]  for x in listings if x.get("followers") is not None]

    return {
        "keyword":              keyword,
        "supply_count":         nb_supply,
        "demand_count_30d":     nb_demand,
        "sample_listing_count": len(listings),
        "sample_sold_count":    len(sold),
        "avg_price_usd":        round(float(np.mean(prices)),      2) if prices      else None,
        "max_price_usd":        round(float(max(prices)),          2) if prices      else None,
        "min_price_usd":        round(float(min(prices)),          2) if prices      else None,
        "avg_sold_price_usd":   round(float(np.mean(sold_prices)), 2) if sold_prices else None,
        "avg_followers":        round(float(np.mean(followers)),   1) if followers   else 0.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 2 — calculate_score
# ══════════════════════════════════════════════════════════════════════════════
# 复用 scorecard.py 的四维权重体系，评分逻辑适配单关键词实时分析。
# scorecard.py 的 min_max_scale 需要多品类才有意义；
# 这里改用基于 archive 市场经验基准的对数归一化，结果可直接与 scorecard 比较。

_WEIGHTS = {
    "supply_demand_score": 0.35,   # 与 scorecard.py WEIGHTS 保持一致
    "velocity_score":      0.30,
    "hype_score":          0.25,
    "momentum_score":      0.10,
}


def _score_supply_demand(supply: int, demand: int) -> tuple[float, float]:
    """
    供需比得分（越低越稀缺）。
    基准：ratio < 3 → ~9 分；ratio = 10 → ~7 分；ratio > 100 → < 2 分
    """
    demand = max(demand, 1)
    ratio  = supply / demand
    score  = max(0.0, min(10.0, 10.0 - np.log1p(ratio) * 2.2))
    return round(ratio, 2), round(score, 2)


def _score_velocity(demand_30d: int) -> float:
    """流通速度：月成交 > 200 件 → 10 分；< 5 件 → 接近 0"""
    return round(min(10.0, np.log1p(demand_30d) / np.log1p(200) * 10), 2)


def _score_hype(avg_followers: float) -> float:
    """收藏热度：均值 > 50 → 10 分"""
    return round(min(10.0, np.log1p(avg_followers) / np.log1p(50) * 10), 2)


def calculate_score(keyword: str, market_data: dict) -> dict:
    """
    复用 scorecard.py 四维评分逻辑，返回：
      供需比、各维度得分(0-10)、加权综合分(0-10)
    当 supply=0 且 demand=0 时（数据完全缺失），返回 error dict。
    """
    print(f"[Tool 2] Calculating score for: '{keyword}'")

    supply        = market_data.get("supply_count",     0)
    demand        = market_data.get("demand_count_30d", 0)
    avg_followers = market_data.get("avg_followers",    0.0)

    if not supply and not demand:
        print(f"  ⚠️  supply=0 且 demand=0，数据不足，跳过评分")
        return {
            "keyword":             keyword,
            "error":               "数据不足，无法评分",
            "total_score":         None,
            "supply_demand_ratio": None,
            "supply_demand_score": None,
            "velocity_score":      None,
            "hype_score":          None,
            "momentum_score":      None,
            "score_breakdown":     None,
        }

    ratio, sd_score = _score_supply_demand(supply, demand)
    vel_score       = _score_velocity(demand)
    hype_score      = _score_hype(avg_followers)
    momentum_score  = 5.0  # 单次快照无历史对比，取中性值

    total = (
        sd_score      * _WEIGHTS["supply_demand_score"] +
        vel_score     * _WEIGHTS["velocity_score"]      +
        hype_score    * _WEIGHTS["hype_score"]           +
        momentum_score * _WEIGHTS["momentum_score"]
    )

    return {
        "keyword":              keyword,
        "supply_demand_ratio":  ratio,
        "supply_demand_score":  sd_score,
        "velocity_score":       vel_score,
        "hype_score":           hype_score,
        "momentum_score":       momentum_score,
        "total_score":          round(total, 2),
        "score_breakdown": {
            "supply_demand": f"{sd_score:.1f}/10  (ratio={ratio}, supply={supply}, demand_30d={demand})",
            "velocity":      f"{vel_score:.1f}/10  (demand_30d={demand})",
            "hype":          f"{hype_score:.1f}/10  (avg_followers={avg_followers})",
            "momentum":      f"{momentum_score:.1f}/10  (N/A – single snapshot)",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 3 — get_price_prediction
# ══════════════════════════════════════════════════════════════════════════════

def get_price_prediction(keyword: str) -> Optional[dict]:
    """
    1. 在 historical_sold.csv（或 sample_historical.csv）里模糊匹配关键词
    2. 有 ≥5 条记录：
       a. 如果关键词能对应 price_model.TARGET_KEYWORDS 里的某个词 → 跑 LR+XGBoost
       b. 否则 → 简单统计（IQR 区间 + 趋势）
    3. 无记录 → 返回 None
    """
    print(f"[Tool 3] Price prediction for: '{keyword}'")

    hist_path = os.path.join(BASE_DIR, "historical_sold.csv")
    if not os.path.exists(hist_path):
        hist_path = os.path.join(BASE_DIR, "sample_historical.csv")
    if not os.path.exists(hist_path):
        print("  No historical CSV found.")
        return None

    try:
        df = pd.read_csv(hist_path)
        kw_lower = keyword.lower()
        mask = df["keyword"].apply(
            lambda x: kw_lower in str(x).lower() or str(x).lower() in kw_lower
        )
        kw_df = df[mask].copy()

        if len(kw_df) < 5:
            print(f"  Only {len(kw_df)} records for '{keyword}' – skipping prediction.")
            return None

        kw_df["sold_date"] = pd.to_datetime(kw_df["sold_date"], errors="coerce")
        kw_df = kw_df.dropna(subset=["sold_date", "sold_price"]).sort_values("sold_date")
        if len(kw_df) < 5:
            return None

        prices = kw_df["sold_price"]
        q25, q75 = float(prices.quantile(0.25)), float(prices.quantile(0.75))
        recent_30d = kw_df[
            kw_df["sold_date"] >= kw_df["sold_date"].max() - pd.Timedelta(days=30)
        ]
        avg_30d = float(
            recent_30d["sold_price"].mean() if len(recent_30d) > 0 else prices.mean()
        )

        # 简单趋势：后半段均价 vs 前半段均价
        mid         = len(kw_df) // 2
        recent_avg  = float(kw_df.iloc[mid:]["sold_price"].mean())
        prior_avg   = float(kw_df.iloc[:mid]["sold_price"].mean())
        pct_change  = (recent_avg - prior_avg) / prior_avg * 100 if prior_avg else 0.0
        trend       = "Rising" if pct_change > 5 else ("Declining" if pct_change < -5 else "Stable")

        # ── 尝试跑完整 price_model ────────────────────────────────────────────
        try:
            import price_model as pm

            matched_kw = next(
                (tk for tk in pm.TARGET_KEYWORDS
                 if kw_lower in tk.lower() or tk.lower() in kw_lower),
                None,
            )
            if matched_kw:
                df_all = pm.load_data()
                if (
                    matched_kw in df_all["keyword"].values
                    and (df_all["keyword"] == matched_kw).sum() >= 10
                ):
                    df_feat = pm.build_features(df_all)

                    orig_targets = pm.TARGET_KEYWORDS[:]
                    pm.TARGET_KEYWORDS = [matched_kw]
                    try:
                        results = pm.train_and_evaluate(df_feat)
                    finally:
                        pm.TARGET_KEYWORDS = orig_targets  # 无论是否报错都恢复

                    if results:
                        r = results[0]
                        return {
                            "keyword":            keyword,
                            "matched_keyword":    matched_kw,
                            "predicted_price":    round(r["predicted_price"], 0),
                            "avg_30d":            round(r["avg_30d"], 0),
                            "trend":              r["trend"],
                            "pct_change":         round(r["pct_change"], 1),
                            "price_range_q25_q75": f"${q25:.0f} – ${q75:.0f}",
                            "n_records":          len(kw_df),
                            "model":              "LR+XGBoost",
                        }
        except Exception as e:
            print(f"  price_model failed ({e}), using simple stats fallback")
        # ── 简单统计兜底 ───────────────────────────────────────────────────────
        return {
            "keyword":             keyword,
            "predicted_price":     round(avg_30d, 0),
            "avg_30d":             round(avg_30d, 0),
            "trend":               trend,
            "pct_change":          round(pct_change, 1),
            "price_range_q25_q75": f"${q25:.0f} – ${q75:.0f}",
            "n_records":           len(kw_df),
            "model":               "simple_stats",
        }

    except Exception as e:
        print(f"  Error in price prediction: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Node 0 — preprocessor_node
# ══════════════════════════════════════════════════════════════════════════════

_TRANSLATE_SYSTEM = (
    "你是一个二手潮牌市场专家。"
    "把用户输入的中文品牌/单品名称转换成Grailed平台的标准英文搜索词。\n"
    "规则：\n"
    "1. 只返回英文搜索词，不要任何解释\n"
    "2. 保留品牌+系列/年份的粒度（不要太泛也不要太精确）\n"
    "3. 俚语和简称要正确识别：\n"
    "   - 马吉拉/马丁 → Maison Margiela\n"
    "   - 巴黎世家/老爹鞋 → Balenciaga Triple S\n"
    "   - 山本 → Yohji Yamamoto\n"
    "   - 川久保玲 → Comme des Garcons\n"
    "   - 九哥/Number Nine → Number Nine\n"
    "   - 赫姆特朗/赫尔穆特 → Helmut Lang\n"
    "4. 如果无法识别，返回原词的拼音或直译"
)


def preprocessor_node(state: MarketAnalysisState) -> dict:
    """检测中文输入，如有则通过 DeepSeek 翻译为 Grailed 英文搜索词"""
    import re
    keyword = state["keyword"]

    if not re.search(r'[一-鿿]', keyword):
        return {"was_translated": False, "original_keyword": ""}

    print(f"[Preprocessor] 检测到中文输入：'{keyword}'，正在翻译…")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[Preprocessor] 未设置 DEEPSEEK_API_KEY，跳过翻译")
        return {"was_translated": False, "original_keyword": ""}

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _TRANSLATE_SYSTEM},
                {"role": "user",   "content": keyword},
            ],
            max_tokens=50,
            temperature=0.1,
        )
        translated = response.choices[0].message.content.strip()
        print(f"[Preprocessor] 翻译结果：'{keyword}' → '{translated}'")
        return {
            "keyword":          translated,
            "original_keyword": keyword,
            "was_translated":   True,
        }
    except Exception as e:
        print(f"[Preprocessor] 翻译失败（{e}），使用原词继续")
        return {"was_translated": False, "original_keyword": ""}


# ══════════════════════════════════════════════════════════════════════════════
# Node 1 — data_fetcher_node
# ══════════════════════════════════════════════════════════════════════════════

def data_fetcher_node(state: MarketAnalysisState) -> dict:
    """抓取市场数据，写入 state['market_data']"""
    market_data = fetch_market_data(state["keyword"])
    return {"market_data": market_data}


# ══════════════════════════════════════════════════════════════════════════════
# Node 1b — validator_node  (fetch_data 之后，supply 不足时放宽关键词)
# ══════════════════════════════════════════════════════════════════════════════

def validator_node(state: MarketAnalysisState) -> dict:
    """
    检查 supply_count；若不足 10 且还有词可去掉，则去掉最后一词并标记重试。
    返回空 dict 表示"数据充足或无需重试"，LangGraph 不更新任何字段。
    """
    supply      = state["market_data"].get("supply_count", 0)
    retry_count = state.get("retry_count", 0)
    keyword     = state["keyword"]

    # 数据充足 / 已达最大重试 / 已是单词 → 不做任何修改
    if supply >= 10 or retry_count >= 2 or len(keyword.strip().split()) <= 1:
        return {}

    relaxed = " ".join(keyword.strip().split()[:-1])
    print(f"[Validator] supply={supply} < 10，放宽关键词：'{keyword}' → '{relaxed}' "
          f"（retry {retry_count+1}/2）")

    update = {
        "keyword":         relaxed,
        "retry_count":     retry_count + 1,
        "keyword_relaxed": True,
    }
    # 只在还没有 original_keyword 时保存（避免覆盖中文翻译前的原词）
    if not state.get("original_keyword"):
        update["original_keyword"] = keyword

    return update


def should_retry(state: MarketAnalysisState) -> str:
    """
    validator 节点之后的条件路由：
      'retry'    → 回到 fetch_data（关键词已被放宽）
      'continue' → 继续到 score
    """
    supply      = state["market_data"].get("supply_count", 0)
    retry_count = state.get("retry_count", 0)
    keyword     = state["keyword"]

    if supply < 10 and retry_count < 2 and len(keyword.split()) > 1:
        return "retry"
    return "continue"


# ══════════════════════════════════════════════════════════════════════════════
# Node 1c — celebrity_signal_node
# ══════════════════════════════════════════════════════════════════════════════

def celebrity_signal_node(state: MarketAnalysisState) -> dict:
    """
    检测明星穿搭催化剂信号（Reddit + Google Trends + Google News RSS）。
    运行在 validator 之后、score 之前，确保使用最终放宽后的关键词。
    超时或报错时静默返回空 dict，不中断主流程。
    """
    print(f"[Node 1c] Detecting celebrity buzz for: '{state['keyword']}' …")
    try:
        from social_signals import fetch_celebrity_buzz

        # 有 DEEPSEEK_API_KEY 时传入 client，启用 LLM 明星名提取；否则纯爬虫模式
        llm_client = None
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            llm_client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        celebrity_data = fetch_celebrity_buzz(state["keyword"], llm_client=llm_client)
        return {"celebrity_data": celebrity_data}
    except Exception as e:
        print(f"[Node 1c] Celebrity signal failed ({e}), continuing without it.")
        return {"celebrity_data": {"buzz_level": "none", "error": str(e)}}


# ══════════════════════════════════════════════════════════════════════════════
# Node 2 — scorer_node
# ══════════════════════════════════════════════════════════════════════════════

def scorer_node(state: MarketAnalysisState) -> dict:
    """计算稀缺度评分 + 价格预测，写入 state['score_data'] / state['price_prediction']"""
    score_data = calculate_score(state["keyword"], state["market_data"])
    if score_data.get("error"):
        kw = state["keyword"]
        return {
            "score_data":       score_data,
            "price_prediction": {},
            "final_report": (
                f"No valid market data found for '{kw}'. "
                "Try a more specific brand + season format, e.g. 'Helmut Lang SS99'."
            ),
        }
    price_pred = get_price_prediction(state["keyword"])
    return {
        "score_data":       score_data,
        "price_prediction": price_pred if price_pred else {},
    }


# ══════════════════════════════════════════════════════════════════════════════
# Node 3 — analyst_node
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = (
    "Please respond in English. You are a professional second-hand archive fashion market analyst, "
    "specialising in the secondary market for Japanese and European designer brands.\n\n"
    "STEP 1 — BRAND VALIDATION:\n"
    "First, assess whether the item belongs to the archive/designer fashion category. "
    "Archive designer brands include (but are not limited to): Helmut Lang, Raf Simons, Number Nine, "
    "Maison Margiela, Carol Christian Poell, Yohji Yamamoto, Comme des Garcons, Julius, "
    "Ann Demeulemeester, Rick Owens, Dries Van Noten, Jil Sander, A.F. Vandevorst, "
    "Issey Miyake, Undercover, Haider Ackermann, Bernhard Willhelm.\n"
    "If the item is a mass-market, sportswear, or mainstream streetwear brand "
    "(e.g. Nike, Adidas, Zara, H&M, Supreme, Palace, Stussy, Uniqlo, fast fashion labels), "
    "begin your response with this exact block:\n"
    "NOTICE: [brand name] is not typically categorized as archive designer fashion. "
    "Data signals may be unreliable due to high volume and mixed product categories. "
    "For best results, try designer brands such as: "
    "Helmut Lang, Raf Simons, Number Nine, Maison Margiela, Carol Christian Poell, Yohji Yamamoto, etc.\n\n"
    "Then continue with the normal analysis below.\n\n"
    "STEP 2 — MARKET ANALYSIS:\n"
    "Based on the provided real-time market data, deliver a concise professional buy/sell recommendation.\n"
    "Your response must cover: 1) Market Status 2) Buy / Hold / Sell Recommendation "
    "3) Suggested Price Range 4) Key Risks\n"
    "If the celebrity signal buzz_level is 'high', add a separate paragraph "
    "'Celebrity Hype Window' naming the celebrity (if available) and the optimal entry timing "
    "(typically within 24–48 hours of peak media buzz).\n"
    "Respond in English, cite specific data points, keep under 300 words."
)


def analyst_node(state: MarketAnalysisState) -> dict:
    """调用 DeepSeek LLM 生成分析报告，写入 state['final_report']"""
    keyword    = state["keyword"]
    market_data = state["market_data"]
    score_data  = state["score_data"]
    price_pred  = state.get("price_prediction", {})

    print(f"[Node 3]  Generating analysis report for: '{keyword}' …")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        report = (
            "[Error] DEEPSEEK_API_KEY not set.\n"
            "Raw market data:\n"
            + json.dumps(market_data, ensure_ascii=False, indent=2)
        )
        return {"final_report": report}

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    data_summary = {
        "Item": keyword,
        "Market Data": {
            "Total Listed":      market_data.get("supply_count"),
            "Sold (30d)":        market_data.get("demand_count_30d"),
            "Avg Price":         f"${market_data.get('avg_price_usd', 'N/A')}",
            "Price Range":       f"${market_data.get('min_price_usd', 'N/A')} – ${market_data.get('max_price_usd', 'N/A')}",
            "Avg Favorites":     market_data.get("avg_followers"),
        },
        "Scarcity Score": {
            "Composite Score":   f"{score_data.get('total_score')}/10",
            "S/D Ratio":         score_data.get("supply_demand_ratio"),
            "Score Breakdown":   score_data.get("score_breakdown"),
        },
        "Price Prediction":   price_pred if price_pred else "No historical data",
        "Celebrity Signal":   state.get("celebrity_data") or {},
    }

    user_msg = (
        "Analyse the following item's market data and provide a professional buy/sell recommendation:\n\n"
        + json.dumps(data_summary, ensure_ascii=False, indent=2)
    )

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        report = response.choices[0].message.content
    except Exception as e:
        report = (
            f"[LLM Error] {e}\n\n"
            f"原始数据摘要:\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}"
        )

    if state.get("was_translated"):
        orig = state.get("original_keyword", "")
        report = f"📝 Input «{orig}» recognised as «{keyword}»\n\n" + report

    if state.get("keyword_relaxed"):
        report = (
            f"⚠️ Insufficient data for original keyword — analysis broadened to «{keyword}»\n\n" + report
        )

    return {"final_report": report}


# ══════════════════════════════════════════════════════════════════════════════
# Build Graph
# ══════════════════════════════════════════════════════════════════════════════

def _route_after_score(state: MarketAnalysisState) -> str:
    """score 节点后：有 error 则直接结束，否则进入 analyze"""
    return "skip" if state["score_data"].get("error") else "analyze"


workflow = StateGraph(MarketAnalysisState)
workflow.add_node("preprocess",       preprocessor_node)
workflow.add_node("fetch_data",       data_fetcher_node)
workflow.add_node("validator",        validator_node)
workflow.add_node("celebrity_signal", celebrity_signal_node)
workflow.add_node("score",            scorer_node)
workflow.add_node("analyze",          analyst_node)

workflow.set_entry_point("preprocess")
workflow.add_edge("preprocess", "fetch_data")
workflow.add_edge("fetch_data", "validator")                 # 每次抓取后都经过验证
workflow.add_conditional_edges("validator", should_retry, {
    "retry":    "fetch_data",                                # 放宽后循环回去重抓
    "continue": "celebrity_signal",                          # 数据充足 → 明星信号检测
})
workflow.add_edge("celebrity_signal", "score")
workflow.add_conditional_edges("score", _route_after_score, {
    "analyze": "analyze",
    "skip":    END,
})
workflow.add_edge("analyze",    END)

app = workflow.compile()


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def analyze_item_full(keyword: str) -> dict:
    """
    对外接口（完整版）：返回完整 state dict
    包含 market_data, score_data, price_prediction, final_report
    供 dashboard.py 调用以同时展示原始数据 + AI 报告
    """
    print(f"\n{'='*60}")
    print(f"  Archive Fashion Market Analyzer")
    print(f"  Keyword : {keyword}")
    print(f"  Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    return app.invoke({
        "keyword":          keyword,
        "original_keyword": "",
        "was_translated":   False,
        "retry_count":      0,
        "keyword_relaxed":  False,
        "market_data":      {},
        "score_data":       {},
        "price_prediction": {},
        "celebrity_data":   {},
        "final_report":     "",
        "messages":         [],
    })


def analyze_item(keyword: str) -> str:
    """
    对外接口：输入关键词 → 返回中文市场分析报告字符串

    示例：
        from agent import analyze_item
        print(analyze_item("Helmut Lang SS99"))
    """
    return analyze_item_full(keyword)["final_report"]


# ══════════════════════════════════════════════════════════════════════════════
# CLI — python agent.py ["keyword"]
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Number Nine AW03"
    report = analyze_item(target)

    print("\n" + "=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)
    print(report)
    print("=" * 60)
