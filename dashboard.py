"""
Archive Selection Dashboard
运行方式：streamlit run dashboard.py
"""

import os
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 页面配置 ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Archive Selection Dashboard",
    page_icon="🧥",
    layout="wide",
)

# ── 全局 CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
/* 整体背景 & 字体 */
[data-testid="stAppViewContainer"] {
    background: #0e0e0e;
    color: #e8e8e8;
}
[data-testid="stSidebar"] {
    background: #161616;
    border-right: 1px solid #2a2a2a;
}
[data-testid="stSidebar"] * { color: #c8c8c8 !important; }

/* 减少默认间距 */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.4rem; }
div[data-testid="column"] { padding: 0 0.3rem; }

/* 页头 */
.dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.4rem 0 0.8rem 0;
    border-bottom: 1px solid #2a2a2a;
    margin-bottom: 0.8rem;
}
.dash-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.02em;
    white-space: nowrap;
}
.dash-meta {
    font-size: 0.78rem;
    color: #666;
    text-align: right;
    line-height: 1.6;
    white-space: nowrap;
    margin-left: 1rem;
}

/* 概览卡片 */
.overview-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 0.8rem;
}
.ov-card {
    background: #151515;
    border: 1px solid #222;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.ov-num {
    font-size: 1.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.2;
}
.ov-num.gold { background: linear-gradient(135deg, #f5c842, #e8a020); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.ov-num.green { background: linear-gradient(135deg, #22c55e, #16a34a); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.ov-num.rose { background: linear-gradient(135deg, #f43f5e, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.ov-label {
    font-size: 0.7rem;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
}
.ov-detail {
    font-size: 0.72rem;
    color: #888;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* KPI 卡片 */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 0.8rem;
}
.kpi-card {
    background: #181818;
    border: 1px solid #262626;
    border-radius: 10px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.kpi-card.gold::before  { background: linear-gradient(90deg, #f5c842, #e8a020); }
.kpi-card.blue::before  { background: linear-gradient(90deg, #3b82f6, #6366f1); }
.kpi-card.rose::before  { background: linear-gradient(90deg, #f43f5e, #ec4899); }
.kpi-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #555;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 0.95rem;
    font-weight: 700;
    color: #ffffff;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.3;
    min-height: 2.6em;
}
.kpi-sub {
    font-size: 0.72rem;
    color: #555;
    margin-top: 2px;
}

/* 区块标题 */
.section-title {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #555;
    margin: 0.6rem 0 0.5rem 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #1f1f1f;
}

/* 自定义表格 */
.dash-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.dash-table thead tr {
    background: #1a1a1a;
    border-bottom: 1px solid #2e2e2e;
}
.dash-table th {
    padding: 7px 10px;
    text-align: left;
    font-weight: 600;
    color: #666;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
}
.dash-table td {
    padding: 7px 10px;
    color: #ccc;
    border-bottom: 1px solid #1e1e1e;
    white-space: nowrap;
}
.dash-table tbody tr:hover { background: #161616; }
.dash-table .rank { color: #444; font-size: 0.72rem; }
.dash-table .name { color: #eee; font-weight: 500; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.score-bar-wrap { width: 46px; background: #1a1a1a; border-radius: 3px; height: 5px; display: inline-block; vertical-align: middle; margin-right: 5px; }
.score-bar-fill { height: 5px; border-radius: 3px; background: linear-gradient(90deg, #1e3a5f, #3b82f6); }
.score-val { vertical-align: middle; color: #3b82f6; font-weight: 600; }
.dash-table th:last-child, .dash-table td:last-child { min-width: 110px; }

/* 底部说明 */
.footer-box {
    background: #131313;
    border: 1px solid #1e1e1e;
    border-radius: 8px;
    padding: 16px 20px;
    margin-top: 0.8rem;
}
.footer-box h4 {
    color: #888;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 10px 0;
}
.footer-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
}
.footer-item .fi-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: #ccc;
    margin-bottom: 3px;
}
.footer-item .fi-weight {
    font-size: 0.68rem;
    color: #3b82f6;
    margin-bottom: 3px;
}
.footer-item .fi-desc {
    font-size: 0.7rem;
    color: #555;
    line-height: 1.45;
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

try:
    df = load_data()
except FileNotFoundError:
    st.error("❌ 找不到 scorecard.csv 或 sample_data.csv，请先运行 `python run_weekly.py` 生成数据。")
    st.stop()

# ── 侧边栏 ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 筛选")
    brands = sorted(df["brand"].unique().tolist())
    selected_brands = st.multiselect(
        "品牌",
        options=brands,
        default=brands,
    )

    st.markdown("---")

    # 评分区间滑块
    score_valid = df["total_score"].dropna()
    score_min_val = float(score_valid.min()) if len(score_valid) > 0 else 0.0
    score_max_val = float(score_valid.max()) if len(score_valid) > 0 else 10.0
    score_range = st.slider(
        "综合得分区间",
        min_value=0.0,
        max_value=10.0,
        value=(score_min_val, score_max_val),
        step=0.1,
        format="%.1f",
    )

    st.markdown("---")
    st.markdown("**评分权重**")
    st.markdown("""
| 维度 | 权重 |
|------|------|
| 供需比 | 35% |
| 流通速度 | 30% |
| 收藏热度 | 25% |
| 价格动量 | 10% |
""")

# ── 筛选 ──────────────────────────────────────────────────────────
filtered = df[df["brand"].isin(selected_brands)].copy()
filtered = filtered[
    (filtered["total_score"] >= score_range[0])
    & (filtered["total_score"] <= score_range[1])
]
filtered = filtered.sort_values("total_score", ascending=False).reset_index(drop=True)

if filtered.empty:
    st.warning("没有符合条件的数据，请在左侧调整筛选条件。")
    st.stop()

top1     = filtered.iloc[0]
scarce   = filtered.loc[filtered["supply_demand_ratio"].idxmin()]
fastest  = filtered.loc[filtered["velocity_30d"].idxmax()]
hottest  = filtered.loc[filtered["avg_followers"].idxmax()]
last_update = df["calc_date"].max().strftime("%Y-%m-%d")
avg_score = filtered["total_score"].mean()

# ── 页头 ──────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-header">
  <div class="dash-title">🧥 Archive Selection Dashboard</div>
  <div class="dash-meta">
    更新日期：{last_update} &nbsp;｜&nbsp;
    追踪单品：{len(filtered)} 件 &nbsp;｜&nbsp; 品牌：{len(selected_brands)} 个
  </div>
</div>
""", unsafe_allow_html=True)

# ── 概览卡片（4列）────────────────────────────────────────────────
fastest_name = fastest['keyword'] if len(fastest['keyword']) <= 24 else fastest['keyword'][:22] + "…"
scarce_name  = scarce['keyword'] if len(scarce['keyword']) <= 24 else scarce['keyword'][:22] + "…"

st.markdown(f"""
<div class="overview-grid">
  <div class="ov-card">
    <div class="ov-label">监控单品</div>
    <div class="ov-num">{len(filtered)}</div>
    <div class="ov-detail">覆盖 {len(selected_brands)} 个品牌</div>
  </div>
  <div class="ov-card">
    <div class="ov-label">平均综合得分</div>
    <div class="ov-num gold">{avg_score:.2f}</div>
    <div class="ov-detail">满分 10.0</div>
  </div>
  <div class="ov-card">
    <div class="ov-label">流通最快</div>
    <div class="ov-num green">{int(fastest['velocity_30d'])}</div>
    <div class="ov-detail" title="{fastest['keyword']}">{fastest_name}</div>
  </div>
  <div class="ov-card">
    <div class="ov-label">最稀缺（供需比最低）</div>
    <div class="ov-num rose">{scarce['supply_demand_ratio']:.1f}x</div>
    <div class="ov-detail" title="{scarce['keyword']}">{scarce_name}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPI 卡片 ──────────────────────────────────────────────────────
st.markdown(f"""
<div class="kpi-grid">
  <div class="kpi-card gold">
    <div class="kpi-label">🥇 综合评分第一</div>
    <div class="kpi-value">{top1['keyword']}</div>
    <div class="kpi-sub">综合得分 {top1['total_score']:.2f} / 10</div>
  </div>
  <div class="kpi-card blue">
    <div class="kpi-label">📦 最稀缺（供需比最低）</div>
    <div class="kpi-value">{scarce['keyword']}</div>
    <div class="kpi-sub">供需比 {scarce['supply_demand_ratio']:.1f}x</div>
  </div>
  <div class="kpi-card rose">
    <div class="kpi-label">🔥 收藏热度最高</div>
    <div class="kpi-value">{hottest['keyword']}</div>
    <div class="kpi-sub">均收藏 {hottest['avg_followers']:.1f}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 排行表格（全宽）──────────────────────────────────────────────
st.markdown('<div class="section-title">📋 单品评分排行榜</div>', unsafe_allow_html=True)

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
<div style="overflow-x:auto; border:1px solid #222; border-radius:8px; max-height:380px; overflow-y:auto; background:#111;">
<table class="dash-table" style="background:#111;">
  <thead><tr>
    <th>#</th><th>单品名</th>
    <th>供需比</th><th>供需得分</th>
    <th>近30天成交</th><th>流通速度</th>
    <th>均收藏</th><th>收藏热度</th>
    <th>价格动量</th><th>综合得分</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</div>"""
st.markdown(table_html, unsafe_allow_html=True)

# ── 中间行：雷达图 + 柱状图 ──────────────────────────────────────
st.markdown('<div class="section-title">📊 单品分析</div>', unsafe_allow_html=True)

col_radar, col_bar = st.columns([1, 1], gap="medium")

with col_radar:
    # 雷达图：选中单品的 4 维对比
    radar_options = filtered["keyword"].tolist()
    radar_default = radar_options[:min(3, len(radar_options))]
    selected_items = st.multiselect(
        "选择单品对比（雷达图）",
        options=radar_options,
        default=radar_default,
        max_selections=5,
    )

    if selected_items:
        categories = ["供需得分", "流通速度", "收藏热度", "价格动量"]
        fig_radar = go.Figure()

        colors = ["#3b82f6", "#f5c842", "#f43f5e", "#22c55e", "#8b5cf6"]
        for idx, item_name in enumerate(selected_items):
            item = filtered[filtered["keyword"] == item_name].iloc[0]
            values = [
                item["supply_demand_score"],
                item["velocity_score"],
                item["grailed_hype_score"],
                item["price_momentum_score"],
            ]
            fig_radar.add_trace(go.Scatterpolar(
                r=values + [values[0]],  # 闭合
                theta=categories + [categories[0]],
                fill="toself",
                fillcolor=colors[idx % len(colors)] + "15",
                line=dict(color=colors[idx % len(colors)], width=2),
                name=item_name if len(item_name) <= 20 else item_name[:18] + "…",
            ))

        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(
                    visible=True, range=[0, 10],
                    gridcolor="#1f1f1f", tickfont=dict(color="#444", size=9),
                ),
                angularaxis=dict(
                    gridcolor="#1f1f1f", tickfont=dict(color="#aaa", size=11),
                ),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#999", size=11),
            legend=dict(
                bgcolor="rgba(0,0,0,0)", font=dict(color="#aaa", size=10),
                orientation="h", yanchor="bottom", y=-0.15,
            ),
            margin=dict(l=40, r=40, t=30, b=40),
            height=380,
            showlegend=True,
        )
        st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.info("请在上方选择单品以显示雷达图")

with col_bar:
    top10 = filtered.head(10).copy()
    top10["label"] = top10["keyword"].apply(
        lambda x: x if len(x) <= 22 else x[:20] + "…"
    )

    fig = go.Figure(go.Bar(
        x=top10["total_score"],
        y=top10["label"],
        orientation="h",
        text=top10["total_score"].apply(lambda v: f"{v:.2f}"),
        textposition="outside",
        textfont=dict(color="#999", size=11),
        marker=dict(
            color=top10["total_score"],
            colorscale=[[0, "#1e3a5f"], [1, "#3b82f6"]],
            line=dict(width=0),
        ),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#999", size=11),
        yaxis=dict(
            categoryorder="total ascending",
            tickfont=dict(color="#ccc", size=10),
            gridcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            gridcolor="#1f1f1f",
            tickfont=dict(color="#555"),
            range=[0, top10["total_score"].max() * 1.2],
        ),
        margin=dict(l=0, r=40, t=30, b=10),
        height=420,
        title=dict(text="Top 10 综合得分", font=dict(color="#555", size=12), x=0.5),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── 散点图 ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🔎 供需比 vs 收藏热度</div>', unsafe_allow_html=True)

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
        "supply_demand_ratio": "供需比（越低越稀缺）",
        "avg_followers": "平均收藏数",
        "brand": "品牌",
    },
    size_max=36,
    color_discrete_sequence=px.colors.qualitative.Bold,
)
fig2.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#999"),
    xaxis=dict(gridcolor="#1f1f1f", tickfont=dict(color="#555")),
    yaxis=dict(gridcolor="#1f1f1f", tickfont=dict(color="#555")),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#aaa")),
    margin=dict(l=0, r=0, t=10, b=10),
    height=340,
)
st.plotly_chart(fig2, use_container_width=True)

# ── 底部说明 ──────────────────────────────────────────────────────
st.markdown("""
<div class="footer-box">
  <h4>📖 指标说明</h4>
  <div class="footer-grid">
    <div class="footer-item">
      <div class="fi-title">供需比 Supply/Demand</div>
      <div class="fi-weight">权重 35%</div>
      <div class="fi-desc">在售数量 ÷ 近30天成交量。比值越低说明供不应求，转售潜力越大。</div>
    </div>
    <div class="footer-item">
      <div class="fi-title">流通速度 Velocity</div>
      <div class="fi-weight">权重 30%</div>
      <div class="fi-desc">近30天实际成交笔数。成交越活跃说明市场流动性越好，出手更容易。</div>
    </div>
    <div class="footer-item">
      <div class="fi-title">收藏热度 Hype</div>
      <div class="fi-weight">权重 25%</div>
      <div class="fi-desc">单品平均被收藏次数。收藏数越高代表买家关注度越强，需求确定性更高。</div>
    </div>
    <div class="footer-item">
      <div class="fi-title">价格动量 Momentum</div>
      <div class="fi-weight">权重 10%</div>
      <div class="fi-desc">近期成交均价 vs 历史均价的变化率。正向动量意味着价格上涨趋势。</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
