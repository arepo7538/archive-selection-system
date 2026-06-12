"""共享数据加载（scorecard + 价格预测）。"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_pipeline_freshness() -> dict | None:
    """pipeline_runs 最近 ok 的 finished_at → 数据年龄。"""
    try:
        from lib import db

        conn = db.connect()
        row = conn.execute(
            "SELECT MAX(finished_at) FROM pipeline_runs WHERE status='ok'"
        ).fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        finished = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        age_days = (datetime.now() - finished).days
        if age_days > 14:
            level = "critical"
        elif age_days > 7:
            level = "warn"
        else:
            level = "ok"
        return {"finished_at": row[0], "age_days": age_days, "level": level}
    except Exception:
        return None


def render_data_age_banner() -> None:
    """>7 天黄条、>14 天红条提醒。"""
    info = get_pipeline_freshness()
    if not info or info["level"] == "ok":
        return
    msg = (
        f"Market data last collected **{info['age_days']} days ago** "
        f"({info['finished_at']}). Run `python run_collect.py` to refresh."
    )
    if info["level"] == "critical":
        st.error(msg)
    else:
        st.warning(msg)


@st.cache_data
def load_scorecard() -> pd.DataFrame:
    """加载 scorecard.csv，缺失时回退到 sample_data.csv。"""
    csv_path = os.path.join(BASE_DIR, "scorecard.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(BASE_DIR, "samples", "sample_data.csv")
    df = pd.read_csv(csv_path)
    df["calc_date"] = pd.to_datetime(df["calc_date"])
    df = df.sort_values("calc_date").groupby("keyword").last().reset_index()
    if "brand" not in df.columns:
        # 兼容旧版 CSV(无 brand 列):退回"前两词"启发式
        df["brand"] = df["keyword"].apply(
            lambda x: " ".join(x.split()[:2]) if len(x.split()) >= 2 else x
        )
    return df


@st.cache_data
def load_prediction_data():
    """跑 price_model 全流程，返回 (results, summary, df_feat)；任何异常返回三个 None。"""
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
