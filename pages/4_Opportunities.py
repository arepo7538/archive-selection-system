"""
Page 4 — Opportunity Radar
库内捡漏:价格低于同品牌同品类中位价 30%+、上架 <14 天、hearts 高于品牌 P80
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from lib import db
from lib.theme import set_page, apply_theme
from lib.data import render_data_age_banner


set_page("Opportunities — Archive Dashboard")
apply_theme()
render_data_age_banner()


@st.cache_data
def load_opportunities() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(
        """
        SELECT brand, title, category, series, price_usd, hearts, url,
               first_seen, created_at
        FROM listings
        WHERE is_active=1 AND suspect_mislabel=0 AND price_usd IS NOT NULL
        """,
        conn,
    )
    conn.close()

    if df.empty:
        return df

    # 上架天数用平台真实上架日 created_at;首轮采集的 first_seen 都是同一天,没有区分度
    df["listed_date"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["listed_date"] = df["listed_date"].fillna(pd.to_datetime(df["first_seen"], errors="coerce"))
    df["days_listed"] = (pd.Timestamp.today().normalize() - df["listed_date"]).dt.days

    medians = (
        df.groupby(["brand", "category"], dropna=False)["price_usd"]
        .median()
        .reset_index(name="median_price")
    )
    p80 = (
        df.groupby("brand")["hearts"]
        .quantile(0.8)
        .reset_index(name="hearts_p80")
    )

    df = df.merge(medians, on=["brand", "category"], how="left")
    df = df.merge(p80, on="brand", how="left")
    df["discount_pct"] = (1 - df["price_usd"] / df["median_price"]) * 100

    deals = df[
        (df["median_price"] > 0)
        & (df["price_usd"] < df["median_price"] * 0.7)
        & (df["days_listed"] < 14)
        & (df["hearts"] > df["hearts_p80"])
    ].copy()

    deals = deals.sort_values("discount_pct", ascending=False)
    return deals


st.markdown(
    '<p class="page-header">OPPORTUNITY RADAR</p>',
    unsafe_allow_html=True,
)
st.markdown("""
<div class="dash-header">
  <div class="dash-title">捡漏雷达</div>
  <div class="dash-meta">低价 × 新鲜上架 × 高收藏 — suspect_mislabel=0</div>
</div>
""", unsafe_allow_html=True)

try:
    deals = load_opportunities()
except Exception as e:
    st.error(f"无法读取 market.db: {e}")
    st.stop()

if deals.empty:
    st.info("当前没有符合捡漏条件的 listing。先运行 `python run_collect.py` 积累数据。")
    st.stop()

with st.sidebar:
    st.markdown("### Filters")
    brands = sorted(deals["brand"].unique().tolist())
    selected = st.multiselect("Brand", options=brands, default=brands)

filtered = deals[deals["brand"].isin(selected)].copy()

st.caption(f"共 {len(filtered)} 条机会 (全库 {len(deals)} 条)")

display = filtered[[
    "title", "price_usd", "median_price", "discount_pct",
    "category", "series", "days_listed", "url",
]].rename(columns={
    "title": "标题",
    "price_usd": "价格",
    "median_price": "中位价",
    "discount_pct": "折扣%",
    "category": "品类",
    "series": "Series",
    "days_listed": "在架天数",
    "url": "Grailed 链接",
})

display["价格"] = display["价格"].map(lambda x: f"${x:,.0f}")
display["中位价"] = display["中位价"].map(lambda x: f"${x:,.0f}")
display["折扣%"] = display["折扣%"].map(lambda x: f"{x:.0f}%")
display["Grailed 链接"] = display["Grailed 链接"].apply(
    lambda u: u if pd.notna(u) else ""
)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Grailed 链接": st.column_config.LinkColumn("Grailed 链接", display_text="打开"),
    },
)
