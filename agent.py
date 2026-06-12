"""
LangGraph ReAct Tool-Calling Agent — Archive Fashion Market Analyzer
====================================================================
Architecture: ReAct (Reasoning + Acting) via langgraph.prebuilt.create_react_agent

Each capability is a @tool-decorated function.
The LLM autonomously decides which tools to call, in what order,
and whether to retry or stop — no hard-coded DAG edges needed.

Tool registry:
  validate_brand          → DeepSeek: is this archive fashion?
  fetch_market_data       → Grailed Algolia: supply / demand / prices
  calculate_scarcity_score → Math: 4-dimension weighted score
  fetch_celebrity_signal  → Wikipedia + Reddit + News: buzz level
  get_price_prediction    → Historical CSV → LR+XGBoost or simple stats

Public API (kept backward-compatible with pages/3_AI_Analysis.py):
  analyze_item_full(keyword)    → dict  (market_data, score_data, final_report …)
  analyze_item(keyword)         → str   (report string only)
  analyze_item_react(keyword)   → str   (ReAct path, same output)
  stream_analyze_react(keyword) → generator of LangGraph stream events

CLI:
  python agent.py "Number Nine AW03"
"""

import os
import sys
import json
import math
import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from openai import OpenAI
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


# ══════════════════════════════════════════════════════════════════════════════
# Tool 1 — validate_brand
# ══════════════════════════════════════════════════════════════════════════════

@tool
def validate_brand(keyword: str) -> dict:
    """
    Validate if the keyword is an archive / designer fashion brand suitable
    for secondary-market analysis on Grailed.

    Returns:
        is_archive (bool)   — True if it qualifies as archive fashion
        confidence (str)    — high / medium / low
        reason (str)        — one-sentence explanation
        suggestions (list)  — 3 archive alternatives when is_archive=False
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        # No key → optimistic pass-through so the pipeline isn't blocked
        return {"is_archive": True, "confidence": "low",
                "reason": "API key not set; validation skipped.", "suggestions": []}

    _SYSTEM = """You are an archive fashion expert.
Determine if the input belongs to archive/designer fashion suitable for
second-hand market analysis on Grailed.

Archive fashion includes: Number Nine, Hysteric Glamour, Undercover,
Neighborhood, Helmut Lang, Raf Simons, Maison Margiela, Carol Christian Poell,
Rick Owens, Ann Demeulemeester, Yohji Yamamoto, Comme des Garcons, Issey Miyake.

NOT archive: Zara, H&M, Uniqlo, Muji, Adidas basics, Nike basics,
Supreme (mainstream), fast fashion, household items.

Respond ONLY with valid JSON (no markdown, no code blocks):
{"is_archive": true/false, "confidence": "high/medium/low",
 "reason": "one sentence", "suggestions": ["alt1","alt2","alt3"]}
Populate suggestions only when is_archive is false."""

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": keyword},
            ],
            max_tokens=150,
            temperature=0.1,
        )
        content = resp.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        # On any error → pass through (never block the pipeline)
        return {"is_archive": True, "confidence": "low",
                "reason": f"Validation error ({e}); defaulting to pass.",
                "suggestions": []}


# ══════════════════════════════════════════════════════════════════════════════
# Tool 2 — fetch_market_data
# ══════════════════════════════════════════════════════════════════════════════

@tool
def fetch_market_data(keyword: str) -> dict:
    """
    Fetch real-time market data from Grailed (via Algolia API) for the keyword.

    Returns:
        supply_count      — total listings on Grailed
        demand_count_30d  — items sold in the last 30 days (sample)
        avg_price_usd     — average listing price
        min_price_usd / max_price_usd
        avg_sold_price_usd
        avg_followers     — average favourites per listing (hype proxy)
        sample_listing_count / sample_sold_count
    """
    from collectors.grailed_search import fetch_grailed_listings, fetch_grailed_sold_30d

    try:
        listings, nb_supply = fetch_grailed_listings(keyword)
        sold,     nb_demand = fetch_grailed_sold_30d(keyword)
    except Exception as e:
        return {"error": str(e), "keyword": keyword,
                "supply_count": 0, "demand_count_30d": 0}

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
# Tool 3 — calculate_scarcity_score
# ══════════════════════════════════════════════════════════════════════════════

@tool
def calculate_scarcity_score(
    supply_count: int,
    demand_count_30d: int,
    avg_followers: float,
) -> dict:
    """
    Calculate a 4-dimension weighted scarcity score (0–10) using archive
    market baselines.

    Weights (mirror scorecard.py):
        Supply/Demand  35%  — log-normalised ratio; lower ratio = higher score
        Velocity       30%  — monthly sold count log-normalised to 200 baseline
        Hype           25%  — avg followers log-normalised to 50 baseline
        Momentum       10%  — fixed neutral 5.0 (no historical snapshot yet)

    Returns individual dimension scores + total_score + supply_demand_ratio.
    """
    from lib.scoring import compute_scarcity_scores_for_agent

    return compute_scarcity_scores_for_agent(
        supply_count, demand_count_30d, avg_followers
    )


# ══════════════════════════════════════════════════════════════════════════════
# Tool 4 — fetch_celebrity_signal
# ══════════════════════════════════════════════════════════════════════════════

@tool
def fetch_celebrity_signal(keyword: str) -> dict:
    """
    Detect celebrity catalyst signals for the keyword via three sources:
      1. Wikipedia Pageviews REST API (primary — no rate limits, cloud-safe)
      2. Reddit old.reddit.com JSON API (fashion subreddits allowlist)
      3. Google News RSS (fallback hype proxy)

    Returns:
        buzz_level        — "high" / "medium" / "low" / "none"
        celebrity_mention — name of celebrity if detected (or null)
        sources           — dict of per-source signal data
    """
    from social_signals import fetch_celebrity_buzz

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    llm_client = None
    if api_key:
        llm_client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    try:
        return fetch_celebrity_buzz(keyword, llm_client=llm_client)
    except Exception as e:
        return {"buzz_level": "none", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Tool 5 — get_price_prediction
# ══════════════════════════════════════════════════════════════════════════════

@tool
def get_price_prediction(keyword: str) -> dict:
    """
    Predict the resale price for the keyword using historical sold data.

    Strategy (in order):
      1. If keyword matches a TARGET_KEYWORDS entry with ≥10 records →
         run full LR + XGBoost pipeline (price_model.py)
      2. Else if ≥5 records found via fuzzy match →
         simple stats: IQR range + first/second half trend
      3. No data → returns predicted_price=None, trend="unknown"

    Returns:
        predicted_price    — USD (int)
        avg_30d            — 30-day average sold price
        trend              — "Rising" / "Stable" / "Declining"
        pct_change         — % change recent vs prior half
        price_range_q25_q75 — "$X – $Y"
        n_records          — number of matched historical records
        model              — "LR+XGBoost" or "simple_stats"
    """
    kw_lower = keyword.lower()
    kw_tok = kw_lower.split()[0] if kw_lower.split() else kw_lower

    try:
        # 数据源:market.db 的 sold_records(品牌级全量,已清洗);失败回退旧 CSV
        kw_df = pd.DataFrame()
        try:
            from lib import db as _db
            _conn = _db.connect()
            kw_df = pd.read_sql_query(
                """SELECT brand AS keyword, sold_price_usd AS sold_price,
                          sold_at AS sold_date
                   FROM sold_records
                   WHERE suspect_mislabel=0 AND sold_price_usd IS NOT NULL
                     AND (brand LIKE ? OR title LIKE ?)""",
                _conn, params=[f"%{kw_tok}%", f"%{kw_lower}%"],
            )
            _conn.close()
        except Exception:
            pass

        if kw_df.empty:
            hist_path = os.path.join(BASE_DIR, "data", "legacy_csv", "historical_sold.csv")
            if not os.path.exists(hist_path):
                hist_path = os.path.join(BASE_DIR, "samples", "sample_historical.csv")
            if not os.path.exists(hist_path):
                return {"predicted_price": None, "trend": "unknown",
                        "reason": "No sold data in DB and no fallback CSV."}
            df = pd.read_csv(hist_path)
            mask = df["keyword"].apply(
                lambda x: kw_lower in str(x).lower() or str(x).lower() in kw_lower
            )
            kw_df = df[mask].copy()

        if len(kw_df) < 5:
            return {"predicted_price": None, "trend": "unknown",
                    "reason": f"Only {len(kw_df)} records — insufficient for prediction."}

        kw_df["sold_date"] = pd.to_datetime(kw_df["sold_date"], errors="coerce")
        kw_df = kw_df.dropna(subset=["sold_date", "sold_price"]).sort_values("sold_date")
        if len(kw_df) < 5:
            return {"predicted_price": None, "trend": "unknown",
                    "reason": "Insufficient clean records after date parse."}

        prices = kw_df["sold_price"]
        q25, q75 = float(prices.quantile(0.25)), float(prices.quantile(0.75))
        recent_30d = kw_df[
            kw_df["sold_date"] >= kw_df["sold_date"].max() - pd.Timedelta(days=30)
        ]
        avg_30d = float(
            recent_30d["sold_price"].mean() if len(recent_30d) > 0 else prices.mean()
        )

        mid        = len(kw_df) // 2
        recent_avg = float(kw_df.iloc[mid:]["sold_price"].mean())
        prior_avg  = float(kw_df.iloc[:mid]["sold_price"].mean()) if mid > 0 else recent_avg
        pct_change = (recent_avg - prior_avg) / prior_avg * 100 if prior_avg else 0.0
        trend      = "Rising" if pct_change > 5 else ("Declining" if pct_change < -5 else "Stable")

        # ── Attempt full LR+XGBoost via price_model ───────────────────────────
        try:
            import price_model as pm
            # 先 load_data:动态 TARGET_KEYWORDS(品牌名)在其中生成,
            # 之后才能做首词模糊匹配("Number Nine AW03" → "Number (N)ine")
            df_all = pm.load_data()
            matched_kw = next(
                (tk for tk in pm.TARGET_KEYWORDS
                 if kw_tok in tk.lower() or tk.lower().split()[0] in kw_lower),
                None,
            )
            if matched_kw:
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
                        pm.TARGET_KEYWORDS = orig_targets
                    if results:
                        r = results[0]
                        return {
                            "keyword":             keyword,
                            "matched_keyword":     matched_kw,
                            "predicted_price":     round(r["predicted_price"], 0),
                            "avg_30d":             round(r["avg_30d"], 0),
                            "trend":               r["trend"],
                            "pct_change":          round(r["pct_change"], 1),
                            "price_range_q25_q75": f"${q25:.0f} – ${q75:.0f}",
                            "n_records":           len(kw_df),
                            "model":               "LR+XGBoost",
                        }
        except Exception as e:
            print(f"  [price_prediction] price_model failed ({e}), using simple stats.")

        # ── Simple stats fallback ─────────────────────────────────────────────
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
        return {"predicted_price": None, "trend": "unknown", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# ReAct Agent — system prompt
# ══════════════════════════════════════════════════════════════════════════════

_REACT_SYSTEM_PROMPT = """You are an expert archive fashion market analyst \
specialising in Japanese and European designer resale markets on Grailed.

WORKFLOW — always follow this exact order:

1. validate_brand(keyword)
   - is_archive=False → explain why, list suggestions, STOP immediately.
   - is_archive=True  → continue.

2. fetch_market_data(keyword)
   - Note if supply_count < 10 (limited data) but always continue.

3. calculate_scarcity_score(supply_count, demand_count_30d, avg_followers)
   - Pass the exact values from step 2.

4. fetch_celebrity_signal(keyword)
   - Check buzz_level for hype catalyst context.

5. get_price_prediction(keyword)
   - Optional but preferred. If it returns predicted_price=None, note "no historical data".

6. Write the final analysis report in English with EXACTLY these sections:

### Recommendation
**Buy / Hold / Sell** — one sentence rationale citing a specific number.

### Market Status
Current supply/demand balance vs typical archive items (2–3 sentences, cite numbers).

### Suggested Price Range
Concrete USD range (e.g. `$180 – $240`) with reasoning tied to step 5 output.

### Key Risks
The single biggest downside, in one sentence.

### Celebrity Hype Window
ONLY include this section when buzz_level = "high".
Name the celebrity and recommend entry within 24–48 h of peak buzz.
Otherwise OMIT this section entirely.

Rules:
- Cite at least one specific number per section.
- Keep the report under 350 words.
- Do NOT add extra top-level sections beyond the ones listed above.
"""


# ══════════════════════════════════════════════════════════════════════════════
# Build agent
# ══════════════════════════════════════════════════════════════════════════════

def _build_react_agent():
    """Construct the ReAct agent. Called once at module load."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key or "placeholder",   # placeholder avoids ChatOpenAI init error
        base_url="https://api.deepseek.com",
        temperature=0.3,
    )
    tools = [
        validate_brand,
        fetch_market_data,
        calculate_scarcity_score,
        fetch_celebrity_signal,
        get_price_prediction,
    ]
    return create_react_agent(llm, tools, prompt=_REACT_SYSTEM_PROMPT)


react_agent = _build_react_agent()


# ══════════════════════════════════════════════════════════════════════════════
# Public API — ReAct paths
# ══════════════════════════════════════════════════════════════════════════════

def analyze_item_react(keyword: str) -> str:
    """
    Run the ReAct agent for a keyword and return the final report string.
    Blocks until the agent finishes (use stream_analyze_react for streaming).
    """
    print(f"\n{'='*60}")
    print(f"  ReAct Archive Analyzer — keyword: {keyword}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    result = react_agent.invoke({
        "messages": [
            {"role": "user",
             "content": f"Analyze this item for archive resale potential: {keyword}"}
        ]
    })
    # The last AI message is the final report
    return result["messages"][-1].content


def stream_analyze_react(keyword: str):
    """
    Stream the ReAct agent analysis, yielding LangGraph update events.
    Each event is a dict like {"agent": {...}} or {"tools": {...}}.

    Example usage in pages/3_AI_Analysis.py:
        for event in stream_analyze_react("Number Nine AW03"):
            node_name = list(event.keys())[0]
            messages = event[node_name].get("messages", [])
    """
    for event in react_agent.stream(
        {"messages": [
            {"role": "user",
             "content": f"Analyze this item for archive resale potential: {keyword}"}
        ]},
        stream_mode="updates",
    ):
        yield event


# ══════════════════════════════════════════════════════════════════════════════
# Public API — backward-compatible shims for pages/3_AI_Analysis.py
# ══════════════════════════════════════════════════════════════════════════════

def analyze_item_full(keyword: str) -> dict:
    """
    Backward-compatible wrapper for dashboard pages.
    Runs the ReAct agent, returns a state-like dict with the same top-level
    keys that pages/3_AI_Analysis.py expects.

    Note: market_data / score_data are empty dicts here because the ReAct
    agent encodes data inside LangChain ToolMessages, not a typed state.
    The dashboard can be updated to parse those if needed.
    """
    print(f"\n{'='*60}")
    print(f"  Archive Fashion Market Analyzer (ReAct)")
    print(f"  Keyword : {keyword}")
    print(f"  Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    report = analyze_item_react(keyword)
    return {
        "keyword":          keyword,
        "original_keyword": "",
        "was_translated":   False,
        "retry_count":      0,
        "keyword_relaxed":  False,
        "market_data":      {},
        "score_data":       {},
        "price_prediction": {},
        "celebrity_data":   {},
        "data_confidence":  {},
        "final_report":     report,
        "messages":         [],
        "rejection_reason": None,
        "suggestions":      [],
    }


def analyze_item(keyword: str) -> str:
    """Convenience wrapper — returns the report string only."""
    return analyze_item_full(keyword)["final_report"]


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Number Nine AW03"
    report = analyze_item(target)

    print("\n" + "=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)
    print(report)
    print("=" * 60)
