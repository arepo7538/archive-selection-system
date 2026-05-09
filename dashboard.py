"""
Archive Selection Dashboard
运行方式：streamlit run dashboard.py
"""

import os
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

# ── 全局 CSS（白色主题）─────────────────────────────────────────────
st.markdown("""
<style>
/* 减少默认间距 */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }

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
    color: #111827;
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
    background: #f9fafb;
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
    background: #ffffff;
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
.kpi-card.gold::before  { background: linear-gradient(90deg, #f59e0b, #d97706); }
.kpi-card.blue::before  { background: linear-gradient(90deg, #3b82f6, #6366f1); }
.kpi-card.rose::before  { background: linear-gradient(90deg, #f43f5e, #ec4899); }
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
    color: #111827;
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
    background: #f9fafb;
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
    color: #374151;
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
}
.dash-table tbody tr:hover { background: #f9fafb; }
.dash-table .rank { color: #9ca3af; font-size: 0.72rem; }
.dash-table .name { color: #111827; font-weight: 500; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.score-bar-wrap { width: 46px; background: #e5e7eb; border-radius: 3px; height: 5px; display: inline-block; vertical-align: middle; margin-right: 5px; }
.score-bar-fill { height: 5px; border-radius: 3px; background: linear-gradient(90deg, #93c5fd, #2563eb); }
.score-val { vertical-align: middle; color: #2563eb; font-weight: 600; }
.dash-table th:last-child, .dash-table td:last-child { min-width: 110px; }

/* 底部说明 */
.footer-box {
    background: #f9fafb;
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
    color: #374151;
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
            return None, None
        df_clean = price_model.remove_outliers(df_raw)
        df_feat = price_model.build_features(df_clean)
        results = price_model.train_and_evaluate(df_feat)
        summary = price_model.build_summary_table(results)
        return results, summary
    except Exception:
        return None, None


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
        options=["Selection Dashboard", "Price Prediction"],
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

    # ── 页头 ──────────────────────────────────────────────────────
    st.markdown("""
    <div class="dash-header">
      <div class="dash-title">Price Prediction</div>
      <div class="dash-meta">
        Linear Regression + XGBoost &nbsp;|&nbsp; 180-day historical data
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 加载预测数据
    with st.spinner("Running price prediction models..."):
        pred_results, pred_summary = load_prediction_data()

    if pred_results is None or pred_summary is None:
        st.warning(
            "Price prediction data unavailable. "
            "Please ensure `historical_sold.csv` exists (run `python historical_scraper.py` first)."
        )
        st.stop()

    # ── 概览卡片 ──────────────────────────────────────────────────
    n_items = len(pred_results)
    n_declining = sum(1 for r in pred_results if r["trend"] == "Declining")
    n_stable = sum(1 for r in pred_results if r["trend"] == "Stable")
    n_rising = sum(1 for r in pred_results if r["trend"] == "Rising")
    avg_mae = np.mean([r.get("xgb_mae", r["lr_mae"]) for r in pred_results])

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

    # ── Summary 表格 ──────────────────────────────────────────────
    st.markdown('<div class="section-title">Prediction Summary</div>', unsafe_allow_html=True)

    TREND_COLORS = {"Declining": "#dc2626", "Stable": "#059669", "Rising": "#2563eb"}

    summary_rows = ""
    for _, srow in pred_summary.iterrows():
        trend = srow["Trend"]
        trend_color = TREND_COLORS.get(trend, "#6b7280")
        trend_icon = {"Rising": "&#9650;", "Declining": "&#9660;", "Stable": "&#8594;"}
        icon = trend_icon.get(trend, "")
        change_val = srow["Change (%)"]
        change_color = "#dc2626" if change_val < -5 else "#059669" if change_val > 5 else "#6b7280"

        test_mae = srow.get('XGB MAE ($)', srow['LR MAE ($)'])
        cv_mae = srow.get('XGB CV MAE ($)', srow.get('LR CV MAE ($)', test_mae))

        summary_rows += f"""
        <tr>
          <td class="name">{srow['Item']}</td>
          <td>{srow['Records']}</td>
          <td style="font-weight:600">${srow['Predicted Price ($)']:.0f}</td>
          <td>${srow['30-Day Avg ($)']:.0f}</td>
          <td style="color:{trend_color}; font-weight:600">{icon} {trend}</td>
          <td style="color:{change_color}; font-weight:600">{change_val:+.1f}%</td>
          <td>${test_mae:.0f}</td>
          <td>${cv_mae:.0f}</td>
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
    """, unsafe_allow_html=True)

    # ── 每个单品的价格走势图 ──────────────────────────────────────
    st.markdown('<div class="section-title">Price Trends — Actual vs Predicted</div>', unsafe_allow_html=True)

    for r in pred_results:
        kw = r["keyword"]
        dates = pd.to_datetime(r["dates"])
        actuals = r["actuals"]
        lr_pred = r["lr_pred_all"]
        split_idx = r["train_size"]
        split_date = dates[split_idx]
        trend = r["trend"]
        trend_color = TREND_COLORS.get(trend, "#6b7280")

        fig = go.Figure()

        # Actual prices (blue dots)
        fig.add_trace(go.Scatter(
            x=dates, y=actuals, mode="markers",
            name="Actual Sold Price",
            marker=dict(color="#2563eb", size=7, opacity=0.7),
        ))

        # LR baseline (gray dashed)
        fig.add_trace(go.Scatter(
            x=dates, y=lr_pred, mode="lines",
            name=f"Linear Regression (MAE=${r['lr_mae']:.0f})",
            line=dict(color="#9ca3af", width=2, dash="dash"),
        ))

        # XGBoost (red solid)
        if "xgb_pred_all" in r:
            fig.add_trace(go.Scatter(
                x=dates, y=r["xgb_pred_all"], mode="lines",
                name=f"XGBoost (MAE=${r['xgb_mae']:.0f})",
                line=dict(color="#dc2626", width=2),
            ))

        # Train/test split line (add_shape to avoid plotly vline bug)
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

        trend_arrow = {"Rising": "&#9650;", "Declining": "&#9660;", "Stable": "&#8594;"}.get(trend, "")

        fig.update_layout(
            title=dict(
                text=f"{kw}  —  Predicted: ${r['predicted_price']:.0f}  ({r['pct_change']:+.1f}%)",
                font=dict(color="#111827", size=14),
            ),
            xaxis_title="Date", yaxis_title="Price (USD)",
            height=380,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#6b7280", size=11),
            xaxis=dict(gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
            yaxis=dict(gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
            margin=dict(l=0, r=20, t=50, b=20),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                bgcolor="rgba(0,0,0,0)", font=dict(color="#374151", size=10),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── MAE 对比柱状图 ────────────────────────────────────────────
    st.markdown('<div class="section-title">Model Comparison — MAE (lower is better)</div>', unsafe_allow_html=True)

    items = [r["keyword"] for r in pred_results]
    lr_maes = [r["lr_mae"] for r in pred_results]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=items, y=lr_maes, name="Linear Regression",
        marker_color="#9ca3af",
        text=[f"${v:.0f}" for v in lr_maes], textposition="outside",
    ))

    if "xgb_mae" in pred_results[0]:
        xgb_maes = [r["xgb_mae"] for r in pred_results]
        fig_bar.add_trace(go.Bar(
            x=items, y=xgb_maes, name="XGBoost",
            marker_color="#dc2626",
            text=[f"${v:.0f}" for v in xgb_maes], textposition="outside",
        ))

    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#6b7280", size=11),
        yaxis=dict(title="MAE ($)", gridcolor="#f3f4f6", tickfont=dict(color="#9ca3af")),
        xaxis=dict(tickfont=dict(color="#374151", size=10)),
        barmode="group",
        height=400,
        margin=dict(l=0, r=20, t=10, b=20),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color="#374151", size=10),
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        ),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── 方法说明 ──────────────────────────────────────────────────
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
          <div class="fi-desc">Time features (week, month, day), item condition, follower count, and 7/14/30-day rolling price averages.</div>
        </div>
        <div class="footer-item">
          <div class="fi-title">Models</div>
          <div class="fi-desc">Linear Regression (baseline) vs XGBoost (gradient-boosted trees). 80/20 chronological train/test split.</div>
        </div>
        <div class="footer-item">
          <div class="fi-title">Trend Signal</div>
          <div class="fi-desc">Compares predicted price vs 30-day avg. &gt;5% = Rising, &lt;-5% = Declining, else Stable.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
