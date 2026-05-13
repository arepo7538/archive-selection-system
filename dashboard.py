"""
Archive Selection Dashboard
运行方式：streamlit run dashboard.py
"""

import os
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 页面配置 ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Archive Selection Dashboard",
    page_icon="🧥",
    layout="wide",
)

# ── 字体强制覆盖（最先加载）──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300;1,9..40,400&display=swap');

* {
    font-family: 'DM Sans', sans-serif !important;
}

html, body, div, span, p, h1, h2, h3, h4, h5, h6,
input, button, select, textarea, label,
[class*="css"], [class*="st-"],
.stApp, .main, .block-container,
[data-testid], [data-baseweb] {
    font-family: 'DM Sans', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# ── 暖白极简主题 CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #f9f7f4 !important;
    color: #1a1a1a !important;
}

[data-testid="stSidebar"] {
    background-color: #f0ede8 !important;
    border-right: 1px solid #e5e0d8 !important;
}

[data-testid="stSidebar"] * {
    color: #1a1a1a !important;
}

[data-testid="stSidebar"] .stButton button {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    color: #374151 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    transition: all 0.15s !important;
    text-align: left !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    background: #ffffff !important;
    border-color: #9ca3af !important;
    color: #111 !important;
}

.main .block-container {
    background-color: #f9f7f4 !important;
    max-width: 1100px !important;
    padding: 2rem 2.5rem !important;
}

[data-testid="metric-container"] {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    border-radius: 12px !important;
    padding: 1.2rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}

[data-testid="metric-container"] label {
    color: #6b7280 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #111827 !important;
    font-size: 28px !important;
    font-weight: 600 !important;
}

h1 {
    font-size: 22px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    letter-spacing: -0.01em !important;
}

h2, h3 {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #6b7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

.stButton > button {
    background: #1a1a1a !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.15s !important;
}

.stButton > button:hover {
    background: #374151 !important;
}

.stTextInput input {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    border-radius: 8px !important;
    color: #1a1a1a !important;
    font-size: 14px !important;
    padding: 0.6rem 1rem !important;
}

.stTextInput input:focus {
    border-color: #9ca3af !important;
    box-shadow: 0 0 0 3px rgba(0,0,0,0.05) !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #e5e0d8 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

hr {
    border-color: #e5e0d8 !important;
    margin: 1.5rem 0 !important;
}

[data-testid="stStatus"] {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    border-radius: 12px !important;
    font-size: 13px !important;
}

.ai-report {
    background: #ffffff;
    border: 1px solid #e5e0d8;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    font-size: 14px;
    line-height: 1.8;
    color: #374151;
}

.page-header {
    font-size: 11px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #9ca3af;
    margin-bottom: 2rem;
    border-bottom: 1px solid #e5e0d8;
    padding-bottom: 1rem;
}

div[data-testid="stVerticalBlock"] > div {
    border-radius: 12px !important;
}

.stSlider > div > div {
    background: #e5e0d8 !important;
}

[data-testid="stProgress"] > div > div > div > div {
    background-color: #374151 !important;
}

[data-testid="stSlider"] div[role="slider"] {
    background-color: #374151 !important;
}
[data-testid="stSlider"] > div > div > div > div {
    background: linear-gradient(to right, #374151, #374151) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background-color: #374151 !important;
    border-color: #374151 !important;
}

[data-baseweb="tag"] {
    background-color: #f3f4f6 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
}
[data-baseweb="tag"] span {
    color: #374151 !important;
}
[data-baseweb="tag"] button {
    color: #9ca3af !important;
}

[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color: #f3f4f6 !important;
    border: 1px solid #d1d5db !important;
    color: #374151 !important;
    border-radius: 6px !important;
}

[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
    color: #374151 !important;
}

[data-testid="stRadio"] label[data-checked="true"] {
    color: #111827 !important;
}

[data-testid="stMetricValue"] {
    color: #111827 !important;
}
</style>
""", unsafe_allow_html=True)

# ── 全局 CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 减少默认间距 */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }

/* 主题适配工具类 */
.metric-value { color: var(--text-color); }
.report-text  { color: var(--text-color); }
.table-label  { color: var(--text-color); opacity: 0.6; }

/* 页头 */
.dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.3rem 0 0.7rem 0;
    border-bottom: 2px solid #e5e7eb;
    margin-bottom: 0.7rem;
}
.dash-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-color);
    letter-spacing: 0.01em;
    white-space: nowrap;
}
.dash-meta {
    font-size: 0.78rem;
    color: #9ca3af;
    text-align: right;
    line-height: 1.5;
    white-space: nowrap;
}

/* 概览卡片 */
.overview-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 0.7rem;
}
.ov-card {
    background: var(--background-color);
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px 14px;
    text-align: center;
}
.ov-num {
    font-size: 1.5rem;
    font-weight: 800;
    color: #2563eb;
    line-height: 1.2;
}
.ov-num.gold   { color: #d97706; }
.ov-num.green  { color: #059669; }
.ov-num.rose   { color: #e11d48; }
.ov-label {
    font-size: 0.68rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 3px;
}
.ov-detail {
    font-size: 0.7rem;
    color: #6b7280;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* KPI 卡片 */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 0.7rem;
}
.kpi-card {
    background: var(--background-color);
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 14px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.kpi-card.gold::before  { background: #d1d5db; }
.kpi-card.blue::before  { background: #d1d5db; }
.kpi-card.rose::before  { background: #d1d5db; }
.kpi-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9ca3af;
    margin-bottom: 3px;
}
.kpi-value {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text-color);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.3;
    min-height: 2.4em;
}
.kpi-sub {
    font-size: 0.7rem;
    color: #9ca3af;
    margin-top: 2px;
}

/* 区块标题 */
.section-title {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9ca3af;
    margin: 0.5rem 0 0.4rem 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #f3f4f6;
}

/* 自定义表格 */
.dash-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.dash-table thead tr {
    background: var(--background-color);
    border-bottom: 2px solid #e5e7eb;
}
.dash-table th {
    padding: 7px 10px;
    text-align: left;
    font-weight: 600;
    color: #6b7280;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
}
.dash-table td {
    padding: 7px 10px;
    color: var(--text-color);
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
}
.dash-table tbody tr:hover { background: var(--background-color); }
.dash-table .rank { color: #9ca3af; font-size: 0.72rem; }
.dash-table .name { color: var(--text-color); font-weight: 500; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.score-bar-wrap { width: 46px; background: #e5e7eb; border-radius: 3px; height: 5px; display: inline-block; vertical-align: middle; margin-right: 5px; }
.score-bar-fill { height: 5px; border-radius: 3px; background: linear-gradient(90deg, #93c5fd, #2563eb); }
.score-val { vertical-align: middle; color: #2563eb; font-weight: 600; }
.dash-table th:last-child, .dash-table td:last-child { min-width: 110px; }

/* 底部说明 */
.footer-box {
    background: var(--background-color);
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 0.6rem;
}
.footer-box h4 {
    color: #6b7280;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 10px 0;
}
.footer-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.footer-item .fi-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text-color);
    margin-bottom: 3px;
}
.footer-item .fi-weight {
    font-size: 0.78rem;
    color: #2563eb;
    margin-bottom: 3px;
}
.footer-item .fi-desc {
    font-size: 0.8rem;
    color: #6b7280;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

# ── 数据加载 ──────────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    csv_path = os.path.join(BASE_DIR, "scorecard.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(BASE_DIR, "sample_data.csv")
    df = pd.read_csv(csv_path)
    df["calc_date"] = pd.to_datetime(df["calc_date"])
    df = df.sort_values("calc_date").groupby("keyword").last().reset_index()
    df["brand"] = df["keyword"].apply(
        lambda x: " ".join(x.split()[:2]) if len(x.split()) >= 2 else x
    )
    return df


@st.cache_data
def load_prediction_data():
    """加载价格预测数据（需要 price_model 模块和 historical_sold.csv）"""
    try:
        import price_model
        df_raw = price_model.load_data()
        if df_raw.empty:
            return None, None, None
        df_clean = price_model.remove_outliers(df_raw)
        df_feat = price_model.build_features(df_clean)
        results = price_model.train_and_evaluate(df_feat)
        summary = price_model.build_summary_table(results)
        for r in results:
            r.pop("lr_model", None)
            r.pop("xgb_model", None)
        return results, summary, df_feat
    except Exception:
        return None, None, None


try:
    df = load_data()
except FileNotFoundError:
    st.error("Cannot find scorecard.csv or sample_data.csv. Please run `python run_weekly.py` first.")
    st.stop()

# ── 侧边栏：页面切换 ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Navigation")
    page = st.radio(
        "Page",
        options=["Selection Dashboard", "Price Prediction", "🤖 AI Analysis"],
        label_visibility="collapsed",
    )
    st.markdown("---")

# ══════════════════════════════════════════════════════════════════
# PAGE 1 — Selection Dashboard
# ══════════════════════════════════════════════════════════════════
if page == "Selection Dashboard":

    # ── 侧边栏筛选器 ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Filters")
        brands = sorted(df["brand"].unique().tolist())
        selected_brands = st.multiselect(
            "Brand",
            options=brands,
            default=brands,
        )
        st.markdown("---")
        score_valid = df["total_score"].dropna()
        score_min_val = float(score_valid.min()) if len(score_valid) > 0 else 0.0
        score_max_val = float(score_valid.max()) if len(score_valid) > 0 else 10.0
        score_range = st.slider(
            "Score Range",
            min_value=0.0,
            max_value=10.0,
            value=(score_min_val, score_max_val),
            step=0.1,
            format="%.1f",
        )
        st.markdown("---")
        st.markdown("**Scoring Weights**")
        st.markdown("""
| Metric | Weight |
|------|------|
| Supply/Demand | 35% |
| Velocity | 30% |
| Hype | 25% |
| Momentum | 10% |
""")

    # ── 筛选 ──────────────────────────────────────────────────────
    filtered = df[df["brand"].isin(selected_brands)].copy()
    filtered = filtered[
        (filtered["total_score"] >= score_range[0])
        & (filtered["total_score"] <= score_range[1])
    ]
    filtered = filtered.sort_values("total_score", ascending=False).reset_index(drop=True)

    if filtered.empty:
        st.warning("No data matches current filters. Please adjust in the sidebar.")
        st.stop()

    top1     = filtered.iloc[0]
    scarce   = filtered.loc[filtered["supply_demand_ratio"].idxmin()]
    fastest  = filtered.loc[filtered["velocity_30d"].idxmax()]
    hottest  = filtered.loc[filtered["avg_followers"].idxmax()]
    last_update = df["calc_date"].max().strftime("%Y-%m-%d")
    avg_score = filtered["total_score"].mean()

    # ── 页头 ──────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="dash-header">
      <div class="dash-title">Archive Selection Dashboard</div>
      <div class="dash-meta">
        Updated: {last_update} &nbsp;|&nbsp;
        Items: {len(filtered)} &nbsp;|&nbsp; Brands: {len(selected_brands)}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 概览卡片（4列）────────────────────────────────────────────
    fastest_name = fastest['keyword'] if len(fastest['keyword']) <= 24 else fastest['keyword'][:22] + "..."
    scarce_name  = scarce['keyword'] if len(scarce['keyword']) <= 24 else scarce['keyword'][:22] + "..."

    st.markdown(f"""
    <div class="overview-grid">
      <div class="ov-card">
        <div class="ov-label">Items Tracked</div>
        <div class="ov-num">{len(filtered)}</div>
        <div class="ov-detail">{len(selected_brands)} brands</div>
      </div>
      <div class="ov-card">
        <div class="ov-label">Avg Score</div>
        <div class="ov-num gold">{avg_score:.2f}</div>
        <div class="ov-detail">out of 10.0</div>
      </div>
      <div class="ov-card">
        <div class="ov-label">Fastest Turnover</div>
        <div class="ov-num green">{int(fastest['velocity_30d'])}</div>
        <div class="ov-detail" title="{fastest['keyword']}">{fastest_name}</div>
      </div>
      <div class="ov-card">
        <div class="ov-label">Most Scarce</div>
        <div class="ov-num rose">{scarce['supply_demand_ratio']:.1f}x</div>
        <div class="ov-detail" title="{scarce['keyword']}">{scarce_name}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI 卡片 ──────────────────────────────────────────────────
    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card gold">
        <div class="kpi-label">Top Ranked</div>
        <div class="kpi-value">{top1['keyword']}</div>
        <div class="kpi-sub">Score {top1['total_score']:.2f} / 10</div>
      </div>
      <div class="kpi-card blue">
        <div class="kpi-label">Most Scarce (Lowest S/D)</div>
        <div class="kpi-value">{scarce['keyword']}</div>
        <div class="kpi-sub">S/D Ratio {scarce['supply_demand_ratio']:.1f}x</div>
      </div>
      <div class="kpi-card rose">
        <div class="kpi-label">Most Hyped</div>
        <div class="kpi-value">{hottest['keyword']}</div>
        <div class="kpi-sub">Avg Followers {hottest['avg_followers']:.1f}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 排行表格（全宽）──────────────────────────────────────────
    st.markdown('<div class="section-title">Ranking</div>', unsafe_allow_html=True)

    rows_html = ""
    for i, row in enumerate(filtered.itertuples(), 1):
        score = row.total_score if pd.notna(row.total_score) else 0
        bar_w = int(score / 10 * 70)
        rows_html += f"""
        <tr>
          <td class="rank">{i}</td>
          <td class="name">{row.keyword}</td>
          <td>{row.supply_demand_ratio:.1f}x</td>
          <td>{row.supply_demand_score:.2f}</td>
          <td>{int(row.velocity_30d)}</td>
          <td>{row.velocity_score:.2f}</td>
          <td>{row.avg_followers:.1f}</td>
          <td>{row.grailed_hype_score:.2f}</td>
          <td>{row.price_momentum_score:.2f}</td>
          <td>
            <span class="score-bar-wrap"><span class="score-bar-fill" style="width:{bar_w}px"></span></span>
            <span class="score-val">{score:.2f}</span>
          </td>
        </tr>"""

    table_html = f"""
    <div style="overflow-x:auto; border:1px solid #e5e7eb; border-radius:8px; max-height:360px; overflow-y:auto;">
    <table class="dash-table">
      <thead><tr>
        <th>#</th><th>Item</th>
        <th>S/D Ratio</th><th>S/D Score</th>
        <th>Sold 30d</th><th>Velocity</th>
        <th>Avg Fav</th><th>Hype</th>
        <th>Momentum</th><th>Total</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>"""
    st.markdown(table_html, unsafe_allow_html=True)

    # ── 中间行：雷达图 + 柱状图 ──────────────────────────────────
    st.markdown('<div class="section-title">Analysis</div>', unsafe_allow_html=True)

    col_radar, col_bar = st.columns([1, 1], gap="medium")

    # 颜色配置（hex + rgba 配对，避免 Plotly fillcolor 不支持 8 位 hex）
    RADAR_COLORS = [
        ("#2563eb", "rgba(37,99,235,0.08)"),
        ("#d97706", "rgba(217,119,6,0.08)"),
        ("#e11d48", "rgba(225,29,72,0.08)"),
        ("#059669", "rgba(5,150,105,0.08)"),
        ("#7c3aed", "rgba(124,58,237,0.08)"),
    ]

    with col_radar:
        radar_options = filtered["keyword"].tolist()
        radar_default = radar_options[:min(3, len(radar_options))]
        selected_items = st.multiselect(
            "Select items to compare",
            options=radar_options,
            default=radar_default,
            max_selections=5,
        )

        if selected_items:
            categories = ["Supply/Demand", "Velocity", "Hype", "Momentum"]
            fig_radar = go.Figure()

            for idx, item_name in enumerate(selected_items):
                item = filtered[filtered["keyword"] == item_name].iloc[0]
                values = [
                    item["supply_demand_score"],
                    item["velocity_score"],
                    item["grailed_hype_score"],
                    item["price_momentum_score"],
                ]
                line_color, fill_color = RADAR_COLORS[idx % len(RADAR_COLORS)]
                fig_radar.add_trace(go.Scatterpolar(
                    r=values + [values[0]],
                    theta=categories + [categories[0]],
                    fill="toself",
                    fillcolor=fill_color,
                    line=dict(color=line_color, width=2),
                    name=item_name if len(item_name) <= 20 else item_name[:18] + "...",
                ))

            fig_radar.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(
                        visible=True, range=[0, 10],
                        gridcolor="#e5e7eb", tickfont=dict(color="#9ca3af", size=9),
                    ),
                    angularaxis=dict(
                        gridcolor="#e5e7eb", tickfont=dict(color="#374151", size=11),
                    ),
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#6b7280", size=11),
                legend=dict(
                    bgcolor="rgba(0,0,0,0)", font=dict(color="#374151", size=10),
                    orientation="h", yanchor="bottom", y=-0.15,
                ),
                margin=dict(l=40, r=40, t=25, b=35),
                height=370,
                showlegend=True,
            )
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.info("Select items above to show radar chart")

    with col_bar:
        top10 = filtered.head(10).copy()
        top10["label"] = top10["keyword"].apply(
            lambda x: x if len(x) <= 22 else x[:20] + "..."
        )

        fig = go.Figure(go.Bar(
            x=top10["total_score"],
            y=top10["label"],
            orientation="h",
            text=top10["total_score"].apply(lambda v: f"{v:.2f}"),
            textposition="outside",
            textfont=dict(color="#6b7280", size=11),
            marker=dict(
                color=top10["total_score"],
                colorscale=[[0, "#93c5fd"], [1, "#2563eb"]],
                line=dict(width=0),
            ),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#6b7280", size=11),
            yaxis=dict(
                categoryorder="total ascending",
                tickfont=dict(color="#374151", size=10),
                gridcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                gridcolor="#f3f4f6",
                tickfont=dict(color="#9ca3af"),
                range=[0, top10["total_score"].max() * 1.2],
            ),
            margin=dict(l=0, r=40, t=25, b=10),
            height=400,
            title=dict(text="Top 10 Score", font=dict(color="#9ca3af", size=12), x=0.5),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── 散点图 ────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Supply/Demand vs Hype</div>', unsafe_allow_html=True)

    scatter_df = filtered.dropna(subset=["supply_demand_ratio", "avg_followers", "total_score"])

    fig2 = px.scatter(
        scatter_df,
        x="supply_demand_ratio",
        y="avg_followers",
        size="total_score",
        color="brand",
        hover_name="keyword",
        hover_data={"total_score": ":.2f", "supply_demand_ratio": ":.1f"},
        labels={
            "supply_demand_ratio": "S/D Ratio (lower = more scarce)",
            "avg_followers": "Avg Followers",
            "brand": "Brand",
        },
        size_max=36,
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#6b7280"),
        xaxis=dict(gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
        yaxis=dict(gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#374151")),
        margin=dict(l=0, r=0, t=10, b=10),
        height=320,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── 底部说明 ──────────────────────────────────────────────────
    st.markdown("""
    <div class="footer-box">
      <h4>Metrics Guide</h4>
      <div class="footer-grid">
        <div class="footer-item">
          <div class="fi-title">Supply/Demand Ratio</div>
          <div class="fi-weight">Weight: 35%</div>
          <div class="fi-desc">Listed count / 30-day sold count. Lower ratio = higher scarcity and resale potential.</div>
        </div>
        <div class="footer-item">
          <div class="fi-title">Velocity</div>
          <div class="fi-weight">Weight: 30%</div>
          <div class="fi-desc">Number of sales in the last 30 days. Higher velocity = better market liquidity.</div>
        </div>
        <div class="footer-item">
          <div class="fi-title">Hype Score</div>
          <div class="fi-weight">Weight: 25%</div>
          <div class="fi-desc">Average followers per listing. More followers = stronger buyer demand signal.</div>
        </div>
        <div class="footer-item">
          <div class="fi-title">Price Momentum</div>
          <div class="fi-weight">Weight: 10%</div>
          <div class="fi-desc">Recent avg price vs historical avg. Positive momentum indicates upward price trend.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 2 — Price Prediction
# ══════════════════════════════════════════════════════════════════
elif page == "Price Prediction":

    # 加载预测数据
    with st.spinner("Running price prediction models..."):
        pred_results, pred_summary, pred_df = load_prediction_data()

    if pred_results is None or pred_summary is None:
        st.warning(
            "Price prediction data unavailable. "
            "Please ensure `historical_sold.csv` exists (run `python historical_scraper.py` first)."
        )
        st.stop()

    TREND_COLORS = {"Declining": "#dc2626", "Stable": "#059669", "Rising": "#2563eb"}
    ITEM_TYPE_COLORS = {
        "jacket": "#dc2626", "pants": "#059669", "hoodie": "#7c3aed",
        "tee": "#2563eb", "shirt": "#d97706", "shoes": "#ec4899", "other": "#9ca3af",
    }
    TYPE_ORDER = ["jacket", "pants", "hoodie", "shirt", "tee", "shoes", "other"]

    _OVERVIEW = "All Items (Overview)"

    # ── 侧边栏：单品选择器 ────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Select Item")
        item_options = [_OVERVIEW] + [r["keyword"] for r in pred_results]
        selected_kw = st.selectbox(
            "Item",
            options=item_options,
            label_visibility="collapsed",
        )

    # ══════════════════════════════════════════════════════════════
    # Overview 总表（默认视图）
    # ══════════════════════════════════════════════════════════════
    if selected_kw == _OVERVIEW:

        # 页头
        n_items = len(pred_results)
        n_declining = sum(1 for r in pred_results if r["trend"] == "Declining")
        n_stable = sum(1 for r in pred_results if r["trend"] == "Stable")
        n_rising = sum(1 for r in pred_results if r["trend"] == "Rising")
        avg_mae = np.mean([r.get("xgb_mae", r["lr_mae"]) for r in pred_results])

        st.markdown("""
        <div class="dash-header">
          <div class="dash-title">Price Prediction — Overview</div>
          <div class="dash-meta">
            Linear Regression + XGBoost &nbsp;|&nbsp; 180-day historical data
          </div>
        </div>
        """, unsafe_allow_html=True)

        # 概览卡片
        st.markdown(f"""
        <div class="overview-grid">
          <div class="ov-card">
            <div class="ov-label">Items Tracked</div>
            <div class="ov-num">{n_items}</div>
            <div class="ov-detail">with 30+ transactions</div>
          </div>
          <div class="ov-card">
            <div class="ov-label">Avg Model MAE</div>
            <div class="ov-num gold">${avg_mae:.0f}</div>
            <div class="ov-detail">XGBoost best model</div>
          </div>
          <div class="ov-card">
            <div class="ov-label">Declining</div>
            <div class="ov-num rose">{n_declining}</div>
            <div class="ov-detail">{n_stable} stable, {n_rising} rising</div>
          </div>
          <div class="ov-card">
            <div class="ov-label">Total Records</div>
            <div class="ov-num green">{sum(r['n_records'] for r in pred_results)}</div>
            <div class="ov-detail">historical transactions</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Summary 总表
        st.markdown('<div class="section-title">Prediction Summary</div>', unsafe_allow_html=True)

        summary_rows = ""
        for _, srow in pred_summary.iterrows():
            s_trend = srow["Trend"]
            s_trend_color = TREND_COLORS.get(s_trend, "#6b7280")
            s_icon = {"Rising": "&#9650;", "Declining": "&#9660;", "Stable": "&#8594;"}.get(s_trend, "")
            s_change = srow["Change (%)"]
            s_change_color = "#dc2626" if s_change < -5 else "#059669" if s_change > 5 else "#6b7280"
            s_test = srow.get('XGB MAE ($)', srow['LR MAE ($)'])
            s_cv = srow.get('XGB CV MAE ($)', srow.get('LR CV MAE ($)', s_test))

            summary_rows += f"""
            <tr>
              <td class="name">{srow['Item']}</td>
              <td>{srow['Records']}</td>
              <td style="font-weight:600">${srow['Predicted Price ($)']:.0f}</td>
              <td>${srow['30-Day Avg ($)']:.0f}</td>
              <td style="color:{s_trend_color}; font-weight:600">{s_icon} {s_trend}</td>
              <td style="color:{s_change_color}; font-weight:600">{s_change:+.1f}%</td>
              <td>${s_test:.0f}</td>
              <td>${s_cv:.0f}</td>
            </tr>"""

        st.markdown(f"""
        <div style="overflow-x:auto; border:1px solid #e5e7eb; border-radius:8px;">
        <table class="dash-table">
          <thead><tr>
            <th>Item</th><th>Records</th>
            <th>Predicted</th><th>30-Day Avg</th>
            <th>Trend</th><th>Change</th><th>Test MAE</th><th>CV MAE</th>
          </tr></thead>
          <tbody>{summary_rows}</tbody>
        </table>
        </div>
        <div style="font-size:0.72rem; color:#9ca3af; margin-top:4px;">
          * Predicted price is a weighted average across item types. Select an item in the sidebar for per-type breakdown.
        </div>
        """, unsafe_allow_html=True)

        # MAE 对比柱状图
        st.markdown('<div class="section-title">Model Comparison — MAE (lower is better)</div>', unsafe_allow_html=True)

        items_list = [r["keyword"] for r in pred_results]
        lr_maes = [r["lr_mae"] for r in pred_results]

        fig_mae = go.Figure()
        fig_mae.add_trace(go.Bar(
            x=items_list, y=lr_maes, name="Linear Regression",
            marker_color="#9ca3af",
            text=[f"${v:.0f}" for v in lr_maes], textposition="outside",
        ))
        if "xgb_mae" in pred_results[0]:
            xgb_maes = [r["xgb_mae"] for r in pred_results]
            fig_mae.add_trace(go.Bar(
                x=items_list, y=xgb_maes, name="XGBoost",
                marker_color="#111827",
                text=[f"${v:.0f}" for v in xgb_maes], textposition="outside",
            ))

        fig_mae.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#6b7280", size=11),
            yaxis=dict(title="MAE ($)", gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
            xaxis=dict(tickfont=dict(color="#374151", size=10)),
            barmode="group", height=380,
            margin=dict(l=0, r=20, t=10, b=20),
            legend=dict(
                bgcolor="rgba(0,0,0,0)", font=dict(color="#374151", size=10),
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            ),
        )
        st.plotly_chart(fig_mae, use_container_width=True)

        # 方法说明
        st.markdown("""
        <div class="footer-box">
          <h4>Methodology</h4>
          <div class="footer-grid">
            <div class="footer-item">
              <div class="fi-title">Data Source</div>
              <div class="fi-desc">180-day historical sold records from Grailed, filtered to items with 30+ transactions.</div>
            </div>
            <div class="footer-item">
              <div class="fi-title">Features</div>
              <div class="fi-desc">Time features, item condition, follower count, item type (jacket/pants/hoodie/tee/shirt/shoes), and 7/14/30-day rolling price averages.</div>
            </div>
            <div class="footer-item">
              <div class="fi-title">Models</div>
              <div class="fi-desc">Linear Regression (baseline) vs XGBoost (conservative: depth=3, n=50, min_child=5). 80/20 chronological split + 3-fold time-series CV.</div>
            </div>
            <div class="footer-item">
              <div class="fi-title">Trend Signal</div>
              <div class="fi-desc">Compares weighted avg predicted price vs 30-day avg. &gt;5% = Rising, &lt;-5% = Declining, else Stable.</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # 单品详情视图
    # ══════════════════════════════════════════════════════════════
    else:

        r = next(r for r in pred_results if r["keyword"] == selected_kw)
        trend = r["trend"]
        trend_color = TREND_COLORS.get(trend, "#6b7280")
        trend_icon = {"Rising": "&#9650;", "Declining": "&#9660;", "Stable": "&#8594;"}[trend]
        test_mae = r.get("xgb_mae", r["lr_mae"])
        cv_mae = r.get("xgb_cv_mae", r.get("lr_cv_mae", test_mae))
        pct = r["pct_change"]
        change_color = "#dc2626" if pct < -5 else "#059669" if pct > 5 else "#6b7280"

        # 页头
        st.markdown(f"""
        <div class="dash-header">
          <div class="dash-title">{selected_kw}</div>
          <div class="dash-meta">
            {r['n_records']} records &nbsp;|&nbsp; 180-day history
          </div>
        </div>
        """, unsafe_allow_html=True)

        # 概览卡片
        st.markdown(f"""
        <div class="overview-grid">
          <div class="ov-card">
            <div class="ov-label">Predicted (Wtd Avg)</div>
            <div class="ov-num">${r['predicted_price']:.0f}</div>
            <div class="ov-detail">across all item types</div>
          </div>
          <div class="ov-card">
            <div class="ov-label">30-Day Avg</div>
            <div class="ov-num gold">${r['avg_30d']:.0f}</div>
            <div class="ov-detail">recent market price</div>
          </div>
          <div class="ov-card">
            <div class="ov-label">Trend</div>
            <div class="ov-num" style="color:{trend_color}">{trend_icon} {trend}</div>
            <div class="ov-detail" style="color:{change_color}">{pct:+.1f}%</div>
          </div>
          <div class="ov-card">
            <div class="ov-label">Model Error</div>
            <div class="ov-num rose">${test_mae:.0f}</div>
            <div class="ov-detail">Test MAE (CV: ${cv_mae:.0f})</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Item Type 预测对比柱状图 + 明细表 ─────────────────────
        tp = r.get("type_predictions", {})
        active_types = [t for t in TYPE_ORDER if t in tp]

        if active_types:
            col_bar, col_table = st.columns([1, 1], gap="medium")

            with col_bar:
                st.markdown('<div class="section-title">Predicted Price by Type</div>', unsafe_allow_html=True)
                type_labels = [t.capitalize() for t in active_types]
                type_preds = [tp[t]["predicted"] for t in active_types]
                type_colors = [ITEM_TYPE_COLORS.get(t, "#9ca3af") for t in active_types]

                fig_tp = go.Figure(go.Bar(
                    x=type_preds,
                    y=type_labels,
                    orientation="h",
                    text=[f"${v:.0f}" for v in type_preds],
                    textposition="outside",
                    textfont=dict(color="#374151", size=11),
                    marker=dict(color=type_colors),
                ))
                fig_tp.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#6b7280", size=11),
                    yaxis=dict(
                        categoryorder="array", categoryarray=list(reversed(type_labels)),
                        tickfont=dict(color="#374151", size=11),
                        gridcolor="rgba(0,0,0,0)",
                    ),
                    xaxis=dict(
                        title="Predicted Price ($)",
                        gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af"),
                        range=[0, max(type_preds) * 1.25] if type_preds else [0, 100],
                    ),
                    margin=dict(l=0, r=40, t=10, b=10),
                    height=max(200, len(active_types) * 50 + 60),
                )
                st.plotly_chart(fig_tp, use_container_width=True)

            with col_table:
                st.markdown('<div class="section-title">Item Type Detail</div>', unsafe_allow_html=True)
                type_rows = ""
                for itype in active_types:
                    info = tp[itype]
                    color = ITEM_TYPE_COLORS.get(itype, "#6b7280")
                    type_rows += f"""
                    <tr>
                      <td><span style="color:{color}; font-weight:600;">&#9679;</span> {itype.capitalize()}</td>
                      <td>{info['count']}</td>
                      <td style="font-weight:600">${info['predicted']:.0f}</td>
                      <td>${info['median']:.0f}</td>
                      <td>${info['min']:.0f} – ${info['max']:.0f}</td>
                    </tr>"""

                st.markdown(f"""
                <div style="border:1px solid #e5e7eb; border-radius:8px;">
                <table class="dash-table">
                  <thead><tr>
                    <th>Type</th><th>Records</th>
                    <th>Predicted</th><th>Median</th><th>Price Range</th>
                  </tr></thead>
                  <tbody>{type_rows}</tbody>
                </table>
                </div>
                """, unsafe_allow_html=True)

        # ── 价格走势散点图（按 item_type 着色）────────────────────
        st.markdown('<div class="section-title">Price Trend — Actual vs Predicted</div>', unsafe_allow_html=True)

        kw_data = pred_df[pred_df["keyword"] == selected_kw].copy()
        dates = pd.to_datetime(r["dates"])
        lr_pred = r["lr_pred_all"]
        split_idx = r["train_size"]
        split_date = dates[split_idx]

        fig = go.Figure()

        for itype in sorted(kw_data["item_type"].unique()):
            sub = kw_data[kw_data["item_type"] == itype]
            color = ITEM_TYPE_COLORS.get(itype, "#9ca3af")
            fig.add_trace(go.Scatter(
                x=sub["sold_date"], y=sub["sold_price"], mode="markers",
                name=itype.capitalize(),
                marker=dict(color=color, size=8, opacity=0.8,
                            line=dict(width=0.5, color="white")),
                legendgroup="types",
            ))

        fig.add_trace(go.Scatter(
            x=dates, y=lr_pred, mode="lines",
            name=f"Linear Regression (MAE=${r['lr_mae']:.0f})",
            line=dict(color="#9ca3af", width=2, dash="dash"),
            legendgroup="models",
        ))

        if "xgb_pred_all" in r:
            fig.add_trace(go.Scatter(
                x=dates, y=r["xgb_pred_all"], mode="lines",
                name=f"XGBoost (MAE=${r.get('xgb_mae', 0):.0f})",
                line=dict(color="#111827", width=2),
                legendgroup="models",
            ))

        fig.add_shape(
            type="line",
            x0=split_date, x1=split_date, y0=0, y1=1,
            yref="paper", line=dict(color="#059669", width=1.5, dash="dot"),
        )
        fig.add_annotation(
            x=split_date, y=1.05, yref="paper",
            text="Train | Test", showarrow=False,
            font=dict(color="#059669", size=10),
        )

        fig.update_layout(
            xaxis_title="Date", yaxis_title="Price (USD)",
            height=420,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#6b7280", size=11),
            xaxis=dict(gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
            yaxis=dict(gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
            margin=dict(l=0, r=20, t=20, b=20),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                bgcolor="rgba(0,0,0,0)", font=dict(color="#374151", size=10),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 3 — AI Analysis
# ══════════════════════════════════════════════════════════════════
elif page == "🤖 AI Analysis":

    # ── Session state 初始化 ──────────────────────────────────────
    if "ai_kw_field" not in st.session_state:
        st.session_state["ai_kw_field"] = ""
    if "ai_result" not in st.session_state:
        st.session_state["ai_result"] = None
    if "ai_history" not in st.session_state:
        st.session_state["ai_history"] = []

    # ── 侧边栏：品牌快选按钮 ──────────────────────────────────────
    with st.sidebar:
        st.markdown("### Quick Select")
        for kw in df["keyword"].tolist():
            label = kw if len(kw) <= 26 else kw[:24] + "…"
            if st.button(label, key=f"qbtn_{kw}", use_container_width=True):
                st.session_state["ai_kw_field"] = kw
                st.rerun()

    # ── 页头 ──────────────────────────────────────────────────────
    st.markdown('<p class="page-header">ARCHIVE MARKET INTELLIGENCE — AI ANALYSIS</p>', unsafe_allow_html=True)
    st.markdown("""
    <div class="dash-header">
      <div class="dash-title">🤖 AI Analysis</div>
      <div class="dash-meta">DeepSeek · Real-time Grailed data · ~60s per query</div>
    </div>
    """, unsafe_allow_html=True)

    # API key check
    if not os.environ.get("DEEPSEEK_API_KEY"):
        st.warning(
            "⚠️ DEEPSEEK_API_KEY not detected. "
            "Run `export DEEPSEEK_API_KEY='your-key'` in your terminal and restart Streamlit."
        )

    # ── Input row: text field + button ───────────────────────────
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

    # ── 触发分析 ──────────────────────────────────────────────────
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
                "final_report": "", "messages": [],
            }
            result = {"keyword": kw}

            try:
                with st.status("🔄 Agent running...", expanded=True) as status:
                    st.write("🌐 **Step 0** — Detecting input language...")

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
                                st.write(f"✅ Step 0 done — Translated **{orig}** → **{translated}**")
                            else:
                                st.write("✅ Step 0 done — English input, searching directly")
                            st.write("🔍 **Step 1** — Fetching live market data (~60s)...")

                        elif node_name == "fetch_data":
                            pass

                        elif node_name == "validator":
                            md = result.get("market_data", {})
                            supply = md.get("supply_count", 0)
                            if node_output.get("keyword_relaxed"):
                                relaxed_kw = node_output.get("keyword", "")
                                st.write(
                                    f"🔄 Low supply ({supply} listings) — broadening keyword to "
                                    f"**'{relaxed_kw}'**, retrying..."
                                )
                            else:
                                demand = md.get("demand_count_30d", 0)
                                s_str  = f"{int(supply):,}" if supply else "?"
                                d_str  = f"{int(demand):,}" if demand else "?"
                                st.write(
                                    f"✅ Step 1 done — **{s_str}** listed, "
                                    f"**{d_str}** sold in last 30 days"
                                )
                                st.write("⭐ **Step 2.5** — Checking celebrity catalyst signals...")

                        elif node_name == "celebrity_signal":
                            buzz   = node_output.get("celebrity_data", {})
                            level  = buzz.get("buzz_level", "none")
                            celeb  = buzz.get("celebrity_mention")
                            if level == "high":
                                mention_str = f"**{celeb}**" if celeb else "celebrity signal"
                                st.write(f"⚡ High-buzz celebrity signal detected! {mention_str}")
                            elif level in ("medium", "low"):
                                st.write(f"✅ Celebrity signal: {level}")
                            else:
                                st.write("✅ No celebrity catalyst detected")
                            st.write("📊 **Step 3** — Calculating scarcity score...")

                        elif node_name == "score":
                            sd    = node_output.get("score_data", {})
                            pp    = node_output.get("price_prediction") or {}
                            score = sd.get("total_score", "?")
                            pred_val = pp.get("predicted_price")
                            pred_str = f", predicted price **${pred_val:.0f}**" if pred_val is not None else ""
                            st.write(f"✅ Step 3 done — Composite score **{score}/10**{pred_str}")
                            st.write("🤖 **Step 4** — AI generating analysis report...")

                        elif node_name == "analyze":
                            st.write("✅ Step 4 done — Report ready")

                    status.update(label="✅ Analysis complete", state="complete")

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

    # ── 结果展示 ──────────────────────────────────────────────────
    if st.session_state.get("ai_result"):
        result      = st.session_state["ai_result"]
        market_data = result.get("market_data", {})
        score_data  = result.get("score_data",  {})
        price_pred  = result.get("price_prediction", {})
        report      = result.get("final_report", "")

        st.markdown('<div class="section-title">Analysis Result</div>', unsafe_allow_html=True)

        if market_data.get("error"):
            st.error(f"Data fetch failed: {market_data['error']}")

        display_kw = result.get("keyword", "")
        col_left, col_right = st.columns([1, 1], gap="medium")

        # ── 左栏：原始市场数据 ────────────────────────────────────
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

            # 评分维度明细
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

        # ── Right column: Brand Background → AI report ───────────
        with col_right:
            with st.expander("Brand Background"):
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
                    st.markdown(st.session_state[cache_key])
                except Exception as _e:
                    st.info(f"Brand background unavailable: {_e}")

            st.markdown("**AI Analysis Report**")
            if report:
                st.markdown(f'<div class="ai-report">{report}</div>', unsafe_allow_html=True)
            else:
                st.info("No report yet")

    # ── Module 2: Market Heat Trend ───────────────────────────────
    st.markdown("### MARKET HEAT TREND")
    try:
        import plotly.graph_objects as _go
        _fig = _go.Figure()

        # Data source 1: Google Trends (with debug output)
        try:
            from social_signals import fetch_google_trends
            _brand_name = (
                " ".join(display_kw.split()[:2])
                if len(display_kw.split()) > 1
                else display_kw
            )
            _trends_data = fetch_google_trends(_brand_name)
            st.write(
                "debug:",
                type(_trends_data),
                _trends_data.columns.tolist() if hasattr(_trends_data, "columns") else _trends_data,
            )
            if _trends_data is not None and len(_trends_data) > 0:
                _weeks  = list(range(len(_trends_data)))
                _values = _trends_data.iloc[:, 0].tolist()
                _fig.add_trace(_go.Scatter(
                    x=_weeks,
                    y=_values,
                    name="Search Interest",
                    line=dict(color="#374151", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(55,65,81,0.08)",
                ))
        except Exception as _te:
            st.write("trends error:", str(_te))

        # Data source 2: Grailed historical_sold.csv
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
                    _fig.add_trace(_go.Scatter(
                        x=_monthly["month_str"],
                        y=_monthly["sales"],
                        name="Monthly Sales (Grailed)",
                        line=dict(color="#9ca3af", width=1.5, dash="dot"),
                        yaxis="y2",
                    ))
        except Exception:
            pass

        _fig.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", size=12, color="#374151"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Week (last 12 months)"),
            yaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Search Interest"),
            yaxis2=dict(overlaying="y", side="right", title="Monthly Sales", showgrid=False),
            hovermode="x unified",
        )

        if len(_fig.data) > 0:
            st.plotly_chart(_fig, use_container_width=True)
            st.caption(
                "Search Interest: Google Trends (normalized 0–100)  ·  "
                "Monthly Sales: Grailed historical data"
            )
        else:
            st.info("Trend data unavailable for this keyword.")

    except Exception as _e:
        st.info(f"Trend chart unavailable: {_e}")

    # ── 历史记录 ──────────────────────────────────────────────────
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

            # 取报告第一段非空文字作预览
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
