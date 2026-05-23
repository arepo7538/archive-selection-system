"""
Page 3 — AI Analysis
用任意关键词触发完整的 LangGraph agent，实时显示节点进度，最终展示：
  Brand Background → Analysis Result (Market Data + AI Report) → Market Heat Trend → History
"""

import sys
import os
import threading
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from lib.theme import set_page, apply_theme
from lib.data import load_scorecard

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


set_page("AI Analysis — Archive Dashboard")
apply_theme()


try:
    df = load_scorecard()
except FileNotFoundError:
    df = pd.DataFrame(columns=["keyword", "brand", "total_score", "calc_date"])


# ── Session state init ───────────────────────────────────────────
if "ai_kw_field" not in st.session_state:
    st.session_state["ai_kw_field"] = ""
if "ai_result" not in st.session_state:
    st.session_state["ai_result"] = None
if "ai_history" not in st.session_state:
    st.session_state["ai_history"] = []


# ── Sidebar: quick-select buttons ────────────────────────────────
with st.sidebar:
    st.markdown("### Quick Select")
    if df.empty:
        st.caption("Run `python run_weekly.py` to populate quick-select keywords.")
    else:
        for kw in df["keyword"].tolist():
            label = kw if len(kw) <= 26 else kw[:24] + "…"
            if st.button(label, key=f"qbtn_{kw}", use_container_width=True):
                st.session_state["ai_kw_field"] = kw
                st.rerun()


# ── Header ───────────────────────────────────────────────────────
st.markdown(
    '<p class="page-header">ARCHIVE MARKET INTELLIGENCE — AI ANALYSIS</p>',
    unsafe_allow_html=True,
)
st.markdown("""
<div class="dash-header">
  <div class="dash-title">AI Analysis</div>
  <div class="dash-meta">DeepSeek · Real-time Grailed data · ~60s per query</div>
</div>
""", unsafe_allow_html=True)

if not os.environ.get("DEEPSEEK_API_KEY"):
    st.warning(
        "DEEPSEEK_API_KEY not detected. "
        "Run `export DEEPSEEK_API_KEY='your-key'` in your terminal and restart Streamlit."
    )


# ── Input row ────────────────────────────────────────────────────
col_input, col_btn = st.columns([5, 1])
with col_input:
    keyword_input = st.text_input(
        "keyword",
        key="ai_kw_field",
        placeholder="Enter any keyword, e.g. Helmut Lang SS99, Number Nine AW03, Balenciaga",
        label_visibility="collapsed",
    )
with col_btn:
    analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

st.caption(
    "Best results with archive designer brands: "
    "Helmut Lang · Raf Simons · Number Nine · Maison Margiela · Yohji Yamamoto"
)


# ── Trigger analysis ─────────────────────────────────────────────
if analyze_clicked:
    kw = (keyword_input or "").strip()
    if not kw:
        st.error("Please enter a keyword before clicking Analyze.")
    elif not os.environ.get("DEEPSEEK_API_KEY"):
        st.error("Please set the DEEPSEEK_API_KEY environment variable before running analysis.")
    else:
        from agent import app as agent_app

        initial_state = {
            "keyword": kw, "original_keyword": "", "was_translated": False,
            "retry_count": 0, "keyword_relaxed": False,
            "market_data": {}, "score_data": {},
            "price_prediction": {}, "celebrity_data": {},
            "data_confidence": {},
            "final_report": "", "messages": [],
            "rejection_reason": None, "suggestions": [],
        }
        result = {"keyword": kw}

        try:
            with st.status("Agent running...", expanded=True) as status:
                st.write("**Step 0** — Detecting input language...")

                for event in agent_app.stream(initial_state, stream_mode="updates"):
                    node_name = list(event.keys())[0]
                    node_output = event[node_name]
                    if node_output is None:
                        continue
                    result.update(node_output)

                    if node_name == "preprocess":
                        if node_output.get("was_translated"):
                            orig = node_output.get("original_keyword", kw)
                            translated = node_output.get("keyword", "")
                            st.write(f"Translated: {orig} → {translated}")

                    elif node_name == "brand_validator":
                        rejection = node_output.get("rejection_reason")
                        if rejection:
                            suggestions = node_output.get("suggestions", [])
                            sugg_str = (
                                " · ".join(suggestions)
                                if suggestions
                                else "Helmut Lang · Raf Simons · Number Nine"
                            )
                            st.warning(
                                f"**Not an archive brand:** {rejection}\n\n"
                                f"Try these instead: {sugg_str}"
                            )
                            status.update(label="Analysis stopped", state="error")
                            break
                        else:
                            st.write("Step 0.5 done — Archive brand verified")
                        st.write("**Step 1** — Fetching live market data (~60s)...")

                    elif node_name == "fetch_data":
                        pass

                    elif node_name == "validator":
                        md = result.get("market_data", {})
                        supply = md.get("supply_count", 0)
                        if node_output.get("keyword_relaxed"):
                            relaxed_kw = node_output.get("keyword", "")
                            st.write(
                                f"Low supply ({supply} listings) — broadening keyword to "
                                f"**'{relaxed_kw}'**, retrying..."
                            )
                        else:
                            demand = md.get("demand_count_30d", 0)
                            s_str  = f"{int(supply):,}" if supply else "?"
                            d_str  = f"{int(demand):,}" if demand else "?"
                            st.write(
                                f"Step 1 done — **{s_str}** listed, "
                                f"**{d_str}** sold in last 30 days"
                            )
                            st.write("**Step 2.5** — Checking celebrity catalyst signals...")

                    elif node_name == "celebrity_signal":
                        buzz   = node_output.get("celebrity_data", {})
                        level  = buzz.get("buzz_level", "none")
                        celeb  = buzz.get("celebrity_mention")
                        if level == "high":
                            mention_str = f"**{celeb}**" if celeb else "celebrity signal"
                            st.write(f"HIGH BUZZ DETECTED — {mention_str}")
                        elif level in ("medium", "low"):
                            st.write(f"Celebrity signal: {level}")
                        else:
                            st.write("No celebrity catalyst detected")
                        st.write("**Step 3** — Calculating scarcity score...")

                    elif node_name == "score":
                        sd    = node_output.get("score_data", {})
                        pp    = node_output.get("price_prediction") or {}
                        score = sd.get("total_score", "?")
                        pred_val = pp.get("predicted_price")
                        pred_str = f", predicted price **${pred_val:.0f}**" if pred_val is not None else ""
                        st.write(f"Step 3 done — Composite score **{score}/10**{pred_str}")
                        st.write("**Step 4** — AI generating analysis report...")

                    elif node_name == "analyze":
                        st.write("Step 4 done — Report ready")

                status.update(label="Analysis complete", state="complete")

            result["keyword"] = kw
            st.session_state["ai_result"] = result
            st.session_state["ai_history"] = [{
                "keyword":     kw,
                "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                "report":      result.get("final_report", ""),
                "market_data": result.get("market_data", {}),
                "score_data":  result.get("score_data",  {}),
            }] + st.session_state["ai_history"]
            st.session_state["ai_history"] = st.session_state["ai_history"][:10]

        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.session_state["ai_result"] = None


# ── Result display ──────────────────────────────────────────────
if st.session_state.get("ai_result"):
    result      = st.session_state["ai_result"]
    market_data = result.get("market_data", {})
    score_data  = result.get("score_data",  {})
    price_pred  = result.get("price_prediction", {})
    report      = result.get("final_report", "")

    if report.startswith("NOT_ARCHIVE:"):
        st.session_state["ai_result"] = None
        st.stop()

    display_kw = result.get("keyword", "")

    # ── 1. Brand Background ─────────────────────────────────────
    st.markdown(
        '<div class="section-title">Brand Background</div>',
        unsafe_allow_html=True,
    )
    with st.container():
        try:
            cache_key = f"brand_bio_{display_kw}"
            if cache_key not in st.session_state:
                from openai import OpenAI as _OAI
                _client = _OAI(
                    api_key=os.environ.get("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com",
                )
                with st.spinner("Loading brand history..."):
                    _resp = _client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": (
                                "You are an archive fashion historian. "
                                "Write a concise 150-word brand background covering: "
                                "1. Founded year and designer "
                                "2. Most iconic era/collection "
                                "3. Why it matters in archive resale market today. "
                                "Write in English, professional but accessible tone."
                            )},
                            {"role": "user", "content": f"Brand/item: {display_kw}"},
                        ],
                        max_tokens=300,
                    )
                st.session_state[cache_key] = _resp.choices[0].message.content
            st.markdown(
                f'<div class="brand-bio">{st.session_state[cache_key]}</div>',
                unsafe_allow_html=True,
            )
        except Exception as _e:
            st.info(f"Brand background unavailable: {_e}")

    st.markdown('<div style="margin-top:1.4rem;"></div>', unsafe_allow_html=True)

    # ── 2. Analysis Result header + Data Confidence Badge ───────
    _conf = result.get("data_confidence") or {}
    _conf_level = _conf.get("level", "low")
    _conf_reason = _conf.get("reason", "no sample data")
    _badge_html = (
        f'<span class="conf-badge conf-{_conf_level}">'
        f'<span class="dot"></span>{_conf_level} confidence'
        f'</span>'
        f'<span class="conf-detail">{_conf_reason}</span>'
    )
    st.markdown(
        f'<div class="section-title" '
        f'style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">'
        f'<span>Analysis Result</span>'
        f'<span style="text-transform:none; letter-spacing:0; border:none;">{_badge_html}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if market_data.get("error"):
        st.error(f"Data fetch failed: {market_data['error']}")

    col_left, col_right = st.columns([1, 1], gap="medium")

    # ── Left: market data ───────────────────────────────────────
    with col_left:
        st.markdown("**Market Data**")
        supply   = market_data.get("supply_count")
        demand   = market_data.get("demand_count_30d")
        avg_px   = market_data.get("avg_price_usd")
        min_px   = market_data.get("min_price_usd")
        max_px   = market_data.get("max_price_usd")
        avg_fol  = market_data.get("avg_followers")
        s_ratio  = score_data.get("supply_demand_ratio")
        total_s  = score_data.get("total_score")

        supply_str = f"{int(supply):,}" if supply is not None else "—"
        demand_str = f"{int(demand):,}" if demand is not None else "—"
        avg_px_str = f"${avg_px:.0f}" if avg_px is not None else "—"
        range_str  = (f"${min_px:.0f} – ${max_px:.0f}"
                      if min_px is not None and max_px is not None else "—")
        fol_str    = f"{avg_fol:.1f}" if avg_fol is not None else "—"
        ratio_str  = f"{s_ratio:.1f}x" if s_ratio is not None else "—"
        score_str  = f"{total_s} / 10" if total_s is not None else "—"

        pred_str = "—"
        if price_pred:
            pp      = price_pred.get("predicted_price")
            trend_v = price_pred.get("trend", "")
            pct_v   = price_pred.get("pct_change", 0)
            if pp is not None:
                pred_str = f"${pp:.0f}  ({trend_v} {pct_v:+.1f}%)"

        st.markdown(f"""
        <div style="border:1px solid #e5e7eb; border-radius:8px; overflow:hidden;">
        <table class="dash-table">
          <tbody>
            <tr><td style="width:50%; opacity:0.65">Listed</td>
                <td style="font-weight:600">{supply_str}</td></tr>
            <tr><td style="opacity:0.65">Sold (30d)</td>
                <td style="font-weight:600">{demand_str}</td></tr>
            <tr><td style="opacity:0.65">Avg Price</td>
                <td style="font-weight:600">{avg_px_str}</td></tr>
            <tr><td style="opacity:0.65">Price Range</td>
                <td style="font-weight:600">{range_str}</td></tr>
            <tr><td style="opacity:0.65">S/D Ratio</td>
                <td style="font-weight:600">{ratio_str}</td></tr>
            <tr><td style="opacity:0.65">Avg Favorites</td>
                <td style="font-weight:600">{fol_str}</td></tr>
            <tr><td style="opacity:0.65">Composite Score</td>
                <td style="font-weight:600; color:#2563eb">{score_str}</td></tr>
            <tr><td style="opacity:0.65">Price Prediction</td>
                <td style="font-weight:600">{pred_str}</td></tr>
          </tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

        if score_data.get("score_breakdown"):
            st.markdown(
                '<div class="section-title" style="margin-top:0.8rem;">Score Breakdown</div>',
                unsafe_allow_html=True,
            )
            for metric, detail in score_data["score_breakdown"].items():
                label = metric.replace("_", " ").replace("score", "").strip().title()
                st.markdown(
                    f'<div style="font-size:0.78rem; color:var(--text-color); opacity:0.7; margin-bottom:5px;">'
                    f'<span style="font-weight:600; color:var(--text-color); opacity:1">{label}</span>: {detail}</div>',
                    unsafe_allow_html=True,
                )

    # ── Right: AI report ────────────────────────────────────────
    with col_right:
        st.markdown("**AI Analysis Report**")
        if report:
            try:
                import markdown as _md
                _report_html = _md.markdown(report, extensions=["extra"])
            except ImportError:
                _report_html = "<p>" + report.replace("\n\n", "</p><p>").replace("\n", "<br/>") + "</p>"
            st.markdown(
                f'<div class="ai-report">{_report_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No report yet")

    # ── 3. Market Heat Trend ────────────────────────────────────
    st.markdown('<div style="margin-top:1.4rem;"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Market Heat Trend</div>',
        unsafe_allow_html=True,
    )

    _hist_plotted = False
    try:
        _hist_path = os.path.join(BASE_DIR, "historical_sold.csv")
        if os.path.exists(_hist_path):
            _hist = pd.read_csv(_hist_path)
            if display_kw in _hist["keyword"].values:
                _kd = _hist[_hist["keyword"] == display_kw].copy()
                _kd["sold_date"] = pd.to_datetime(_kd["sold_date"])
                _monthly = (
                    _kd.groupby(_kd["sold_date"].dt.to_period("M"))
                    .size()
                    .reset_index()
                )
                _monthly.columns = ["month", "sales"]
                _monthly["month_str"] = _monthly["month"].astype(str)
                _fig_hist = go.Figure()
                _fig_hist.add_trace(go.Scatter(
                    x=_monthly["month_str"], y=_monthly["sales"],
                    name="Monthly Sales (Grailed)",
                    mode="lines+markers",
                    line=dict(color="#374151", width=2),
                    fill="tozeroy", fillcolor="rgba(55,65,81,0.08)",
                ))
                _fig_hist.update_layout(
                    height=240,
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="DM Sans", size=11, color="#374151"),
                    xaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
                    yaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Monthly Sales"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    hovermode="x unified",
                )
                st.plotly_chart(_fig_hist, use_container_width=True)
                st.caption("Monthly sold count from Grailed historical data (180-day window)")
                _hist_plotted = True
    except Exception:
        pass

    if not _hist_plotted:
        st.info(
            "No historical sales data available. "
            "Run `python historical_scraper.py` to collect data."
        )

    # ── Topic Interest — Wikipedia Pageviews（云端稳定，替代 Google Trends） ─
    # 之前用 pytrends 在 Streamlit Cloud 共享 IP 上几乎必被 429 限流，导致这块图永远空白。
    # 改用 Wikipedia REST API，免 key、几乎不限流，且 90 天日级数据可画时间序列。
    def _get_wiki(brand_name, result_container):
        try:
            from social_signals import fetch_wikipedia_pageviews
            result_container["data"] = fetch_wikipedia_pageviews(brand_name, days=90)
            result_container["error"] = None
        except Exception as _e:
            result_container["data"] = None
            result_container["error"] = str(_e)

    _topic_result = {}
    _brand_name = (
        " ".join(display_kw.split()[:2])
        if len(display_kw.split()) > 1
        else display_kw
    )

    _topic_placeholder = st.empty()
    with _topic_placeholder.container():
        st.info("Loading topic interest (Wikipedia)…")

    _t = threading.Thread(target=_get_wiki, args=(_brand_name, _topic_result))
    _t.start()
    _t.join(timeout=12)

    with _topic_placeholder.container():
        data = _topic_result.get("data")
        if data and data.get("daily"):
            daily = data["daily"]
            xs = [pd.to_datetime(d["date"], format="%Y%m%d") for d in daily]
            ys = [d["views"] for d in daily]
            ratio       = data.get("trends_ratio") or 1.0
            recent_4w   = data.get("trends_recent_4w") or 0
            baseline    = data.get("trends_historical") or 0
            article     = data.get("article") or _brand_name

            _fig = go.Figure()
            _fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="lines",
                line=dict(color="#374151", width=2),
                fill="tozeroy",
                fillcolor="rgba(55,65,81,0.08)",
                hovertemplate="%{x|%Y-%m-%d}: %{y:,} views<extra></extra>",
                name="Daily views",
            ))
            _fig.add_hline(
                y=baseline, line=dict(color="#9ca3af", width=1, dash="dot"),
                annotation_text=f"90-day avg: {baseline:.0f}",
                annotation_position="top right",
                annotation_font_color="#9ca3af",
                annotation_font_size=10,
            )
            _fig.update_layout(
                height=240,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans", size=11, color="#374151"),
                xaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
                yaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Daily Wikipedia Views"),
                showlegend=False,
                hovermode="x unified",
            )
            st.plotly_chart(_fig, use_container_width=True)

            if ratio >= 1.3:
                msg = f"Recent 4-week avg {recent_4w:.0f} views — **{ratio:.2f}x** above baseline · rising momentum"
            elif ratio >= 1.1:
                msg = f"Recent 4-week avg {recent_4w:.0f} views — {ratio:.2f}x above baseline · slight uptick"
            elif ratio <= 0.8:
                msg = f"Recent 4-week avg {recent_4w:.0f} views — {ratio:.2f}x of baseline · cooling down"
            else:
                msg = f"Recent 4-week avg {recent_4w:.0f} views — stable at {ratio:.2f}x baseline"
            st.caption(f"Wikipedia Topic Interest — *{article}* · {msg}")
        elif _topic_result.get("error"):
            st.caption(f"Topic interest unavailable: {_topic_result['error']}")
        else:
            st.caption(
                "Topic interest: no Wikipedia article found for this brand "
                "(very niche labels often lack an English Wikipedia page)."
            )


# ── History (always visible) ─────────────────────────────────────
history = st.session_state.get("ai_history", [])
if history:
    st.markdown("---")
    hist_hdr, clear_col = st.columns([6, 1])
    with hist_hdr:
        st.markdown(
            '<div class="section-title">Recent Analysis History</div>',
            unsafe_allow_html=True,
        )
    with clear_col:
        if st.button("Clear History", key="clear_ai_history"):
            st.session_state["ai_history"] = []
            st.session_state["ai_result"]  = None
            st.rerun()

    for entry in history[:3]:
        kw_e   = entry["keyword"]
        ts_e   = entry["timestamp"]
        rpt_e  = entry.get("report", "")
        md_e   = entry.get("market_data", {})
        sd_e   = entry.get("score_data",  {})

        preview = next(
            (ln.strip().lstrip("#*- ") for ln in rpt_e.split("\n") if ln.strip()),
            "",
        )
        if len(preview) > 110:
            preview = preview[:108] + "…"

        sup_e   = md_e.get("supply_count")
        dem_e   = md_e.get("demand_count_30d")
        scr_e   = sd_e.get("total_score")
        sup_str = f"{int(sup_e):,}" if sup_e is not None else "—"
        dem_str = f"{int(dem_e):,}" if dem_e is not None else "—"
        scr_str = str(scr_e) if scr_e is not None else "—"

        st.markdown(f"""
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:12px 16px;
                    margin-bottom:8px; background:var(--background-color);">
          <div style="display:flex; justify-content:space-between;
                      align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:4px;">
            <span style="font-weight:700; color:var(--text-color); font-size:0.88rem;">{kw_e}</span>
            <span style="font-size:0.72rem; color:#9ca3af; white-space:nowrap;">
              {ts_e} &nbsp;·&nbsp; Listed {sup_str} &nbsp;·&nbsp;
              Sold {dem_str} &nbsp;·&nbsp; Score {scr_str}/10
            </span>
          </div>
          <div style="font-size:0.80rem; color:var(--text-color); opacity:0.65; line-height:1.5;">{preview}</div>
        </div>
        """, unsafe_allow_html=True)
