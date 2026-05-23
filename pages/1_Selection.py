"""
Page 1 — Selection Dashboard
排行 / 雷达 / 散点。从 scorecard.csv 读取。
"""

import sys
import os

# 把项目根目录加入 sys.path，使得 lib / price_model / agent 等可被 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from lib.theme import set_page, apply_theme
from lib.data import load_scorecard


set_page("Selection — Archive Dashboard")
apply_theme()

try:
    df = load_scorecard()
except FileNotFoundError:
    st.error(
        "Cannot find scorecard.csv or sample_data.csv. "
        "Please run `python run_weekly.py` first."
    )
    st.stop()


# ── Sidebar filters ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")
    brands = sorted(df["brand"].unique().tolist())
    selected_brands = st.multiselect("Brand", options=brands, default=brands)
    st.markdown("---")
    score_valid = df["total_score"].dropna()
    score_min_val = float(score_valid.min()) if len(score_valid) > 0 else 0.0
    score_max_val = float(score_valid.max()) if len(score_valid) > 0 else 10.0
    score_range = st.slider(
        "Score Range",
        min_value=0.0, max_value=10.0,
        value=(score_min_val, score_max_val),
        step=0.1, format="%.1f",
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


# ── Filter ───────────────────────────────────────────────────────
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


# ── Header ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-header">
  <div class="dash-title">Archive Selection Dashboard</div>
  <div class="dash-meta">
    Updated: {last_update} &nbsp;|&nbsp;
    Items: {len(filtered)} &nbsp;|&nbsp; Brands: {len(selected_brands)}
  </div>
</div>
""", unsafe_allow_html=True)


# ── Overview cards ───────────────────────────────────────────────
fastest_name = fastest['keyword'] if len(fastest['keyword']) <= 24 else fastest['keyword'][:22] + "..."
scarce_name  = scarce['keyword']  if len(scarce['keyword'])  <= 24 else scarce['keyword'][:22]  + "..."

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


# ── KPI cards ────────────────────────────────────────────────────
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


# ── Ranking table ────────────────────────────────────────────────
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

st.markdown(f"""
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
</div>""", unsafe_allow_html=True)


# ── Radar + Bar ──────────────────────────────────────────────────
st.markdown('<div class="section-title">Analysis</div>', unsafe_allow_html=True)
col_radar, col_bar = st.columns([1, 1], gap="medium")

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
        options=radar_options, default=radar_default, max_selections=5,
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
                fill="toself", fillcolor=fill_color,
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
            height=370, showlegend=True,
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
        x=top10["total_score"], y=top10["label"], orientation="h",
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


# ── Scatter ──────────────────────────────────────────────────────
st.markdown('<div class="section-title">Supply/Demand vs Hype</div>', unsafe_allow_html=True)

scatter_df = filtered.dropna(subset=["supply_demand_ratio", "avg_followers", "total_score"])
fig2 = px.scatter(
    scatter_df,
    x="supply_demand_ratio", y="avg_followers",
    size="total_score", color="brand",
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


# ── Footer guide ─────────────────────────────────────────────────
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
