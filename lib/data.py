"""共享数据加载（scorecard + 价格预测）。"""

import os
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@st.cache_data
def load_scorecard() -> pd.DataFrame:
    """加载 scorecard.csv，缺失时回退到 sample_data.csv。"""
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
