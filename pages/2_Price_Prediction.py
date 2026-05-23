"""
Page 2 — Price Prediction
LR + XGBoost 训练，按 item 详情或总览展示。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from lib.theme import set_page, apply_theme
from lib.data import load_prediction_data


set_page("Price Prediction — Archive Dashboard")
apply_theme()


with st.spinner("Running price prediction models..."):
    pred_results, pred_summary, pred_df = load_prediction_data()

if pred_results is None or pred_summary is None or not pred_results:
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


# ── Sidebar item selector ────────────────────────────────────────
with st.sidebar:
    st.markdown("### Select Item")
    item_options = [_OVERVIEW] + [r["keyword"] for r in pred_results]
    selected_kw = st.selectbox("Item", options=item_options, label_visibility="collapsed")


# ══════════════════════════════════════════════════════════════════
# Overview
# ══════════════════════════════════════════════════════════════════
if selected_kw == _OVERVIEW:
    n_items = len(pred_results)
    n_declining = sum(1 for r in pred_results if r["trend"] == "Declining")
    n_stable    = sum(1 for r in pred_results if r["trend"] == "Stable")
    n_rising    = sum(1 for r in pred_results if r["trend"] == "Rising")
    avg_mae = np.mean([r.get("xgb_mae", r["lr_mae"]) for r in pred_results])

    st.markdown("""
    <div class="dash-header">
      <div class="dash-title">Price Prediction — Overview</div>
      <div class="dash-meta">
        Linear Regression + XGBoost &nbsp;|&nbsp; 180-day historical data
      </div>
    </div>
    """, unsafe_allow_html=True)

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

    st.markdown('<div class="section-title">Model Comparison — MAE (lower is better)</div>',
                unsafe_allow_html=True)

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


# ══════════════════════════════════════════════════════════════════
# Detail view
# ══════════════════════════════════════════════════════════════════
else:
    r = next(r for r in pred_results if r["keyword"] == selected_kw)
    trend = r["trend"]
    trend_color = TREND_COLORS.get(trend, "#6b7280")
    trend_icon = {"Rising": "&#9650;", "Declining": "&#9660;", "Stable": "&#8594;"}[trend]
    test_mae = r.get("xgb_mae", r["lr_mae"])
    cv_mae = r.get("xgb_cv_mae", r.get("lr_cv_mae", test_mae))
    pct = r["pct_change"]
    change_color = "#dc2626" if pct < -5 else "#059669" if pct > 5 else "#6b7280"

    st.markdown(f"""
    <div class="dash-header">
      <div class="dash-title">{selected_kw}</div>
      <div class="dash-meta">
        {r['n_records']} records &nbsp;|&nbsp; 180-day history
      </div>
    </div>
    """, unsafe_allow_html=True)

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

    tp = r.get("type_predictions", {})
    active_types = [t for t in TYPE_ORDER if t in tp]

    if active_types:
        col_bar, col_table = st.columns([1, 1], gap="medium")

        with col_bar:
            st.markdown('<div class="section-title">Predicted Price by Type</div>',
                        unsafe_allow_html=True)
            type_labels = [t.capitalize() for t in active_types]
            type_preds = [tp[t]["predicted"] for t in active_types]
            type_colors = [ITEM_TYPE_COLORS.get(t, "#9ca3af") for t in active_types]

            fig_tp = go.Figure(go.Bar(
                x=type_preds, y=type_labels, orientation="h",
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
                    categoryorder="array",
                    categoryarray=list(reversed(type_labels)),
                    tickfont=dict(color="#374151", size=11),
                    gridcolor="rgba(0,0,0,0)",
                ),
                xaxis=dict(
                    title="Predicted Price ($)",
                    gridcolor="#f3f4f6",
                    tickfont=dict(color="#9ca3af"),
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

    # ── Trend scatter ───────────────────────────────────────────
    st.markdown('<div class="section-title">Price Trend — Actual vs Predicted</div>',
                unsafe_allow_html=True)

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
        x0=split_date, x1=split_date, y0=0, y1=1, yref="paper",
        line=dict(color="#059669", width=1.5, dash="dot"),
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
