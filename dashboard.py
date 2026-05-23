"""
Archive Selection Dashboard — 入口
运行: streamlit run dashboard.py

应用拆成三个 page，分别在 pages/ 目录下：
  1_Selection.py        排行 / 雷达 / 散点
  2_Price_Prediction.py LR + XGBoost 训练与详情
  3_AI_Analysis.py      LangGraph agent 实时分析

Streamlit 会自动扫描 pages/ 目录，把侧边栏导航生成出来。
本入口文件只负责：注入主题 CSS、欢迎页文案、指引用户去左侧 nav 选页。
"""

import os
from datetime import datetime
import pandas as pd
import streamlit as st

from lib.theme import set_page, apply_theme
from lib.data import load_scorecard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


set_page("Archive Selection Dashboard")
apply_theme()


# ── Header ───────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
  <div class="dash-title">Archive Selection System</div>
  <div class="dash-meta">Quantitative archive fashion resale intelligence</div>
</div>
""", unsafe_allow_html=True)


# ── Data freshness overview ──────────────────────────────────────
_data_ok = False
try:
    df = load_scorecard()
    _data_ok = True
    last_update = df["calc_date"].max().strftime("%Y-%m-%d")
    n_items = len(df)
    n_brands = df["brand"].nunique()
    avg_score = df["total_score"].mean()
    top_kw = df.sort_values("total_score", ascending=False).iloc[0]["keyword"]
except FileNotFoundError:
    last_update = "—"
    n_items = n_brands = 0
    avg_score = 0
    top_kw = "—"


_hist_records = 0
_hist_path = os.path.join(BASE_DIR, "historical_sold.csv")
if os.path.exists(_hist_path):
    try:
        _hist_records = len(pd.read_csv(_hist_path))
    except Exception:
        pass


st.markdown(f"""
<div class="overview-grid">
  <div class="ov-card">
    <div class="ov-label">Tracked Items</div>
    <div class="ov-num">{n_items}</div>
    <div class="ov-detail">{n_brands} brands</div>
  </div>
  <div class="ov-card">
    <div class="ov-label">Avg Score</div>
    <div class="ov-num gold">{avg_score:.2f}</div>
    <div class="ov-detail">out of 10.0</div>
  </div>
  <div class="ov-card">
    <div class="ov-label">Historical Records</div>
    <div class="ov-num green">{_hist_records:,}</div>
    <div class="ov-detail">180-day sold history</div>
  </div>
  <div class="ov-card">
    <div class="ov-label">Last Updated</div>
    <div class="ov-num rose" style="font-size:1.1rem;">{last_update}</div>
    <div class="ov-detail">scorecard refresh</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Page guide ───────────────────────────────────────────────────
st.markdown('<div class="section-title">Navigate</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="kpi-grid">
  <div class="kpi-card gold">
    <div class="kpi-label">1 · Selection Dashboard</div>
    <div class="kpi-value">Rank archive items by composite score</div>
    <div class="kpi-sub">Top now: {top_kw}</div>
  </div>
  <div class="kpi-card blue">
    <div class="kpi-label">2 · Price Prediction</div>
    <div class="kpi-value">LR + XGBoost forecasts on 180-day history</div>
    <div class="kpi-sub">Per-item type breakdown</div>
  </div>
  <div class="kpi-card rose">
    <div class="kpi-label">3 · AI Analysis</div>
    <div class="kpi-value">Live agent — any keyword, structured report</div>
    <div class="kpi-sub">DeepSeek + Reddit + Google Trends</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.caption("Use the sidebar to switch between pages. Each page loads its own data lazily.")


# ── Methodology block (kept from old footer) ─────────────────────
st.markdown("""
<div class="footer-box">
  <h4>How It Works</h4>
  <div class="footer-grid">
    <div class="footer-item">
      <div class="fi-title">Data Pipeline</div>
      <div class="fi-desc">Grailed Algolia API → CSV cache. Weekly refresh via <code>run_weekly.py</code>.</div>
    </div>
    <div class="footer-item">
      <div class="fi-title">Scoring</div>
      <div class="fi-desc">Composite: S/D Ratio 35% + Velocity 30% + Hype 25% + Momentum 10%.</div>
    </div>
    <div class="footer-item">
      <div class="fi-title">ML Models</div>
      <div class="fi-desc">Linear Regression + XGBoost. Time-series split, 3-fold CV.</div>
    </div>
    <div class="footer-item">
      <div class="fi-title">Agent</div>
      <div class="fi-desc">LangGraph node DAG: preprocess → validator → fetch → score → analyze.</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


if not _data_ok:
    st.warning(
        "No scorecard data found. Run `python run_weekly.py` to populate "
        "`scorecard.csv` before opening the Selection or AI Analysis pages."
    )
