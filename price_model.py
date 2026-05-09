"""
Price Prediction Model
基于 historical_sold.csv 训练线性回归 + XGBoost 模型
预测 archive 单品成交价格趋势

用法: import price_model; results = price_model.run()
"""

import os
import re
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from typing import Optional

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("Warning: xgboost not installed, will skip XGBoost model.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据量 >= 30 的单品
TARGET_KEYWORDS = [
    "Number Nine AW03",
    "Number Nine AW09",
    "Vetements oversized hoodie",
    "Helmut Lang SS99",
    "Prada bowling shirt",
]

CONDITION_MAP = {
    "is_new": 4,
    "is_gently_used": 3,
    "is_used": 2,
    "is_worn": 1,
}

# ── Item Type 分类（按 title 关键词匹配）──────────────────────────
ITEM_TYPE_PATTERNS = [
    ("jacket",  r"jacket|bomber|varsity|blazer|ma-1|flight|coat"),
    ("pants",   r"pants|jeans|denim(?!.*jacket)|trouser|bondage.*jean"),
    ("hoodie",  r"hoodie|hoody|sweatshirt"),
    ("tee",     r"t-?shirt|tee\b|tshirt"),
    ("shirt",   r"shirt(?!.*t-shirt)"),
    ("shoes",   r"shoe|sneaker|converse|boot"),
]

ITEM_TYPE_MAP = {
    "jacket": 6, "pants": 5, "hoodie": 4,
    "shirt": 3, "tee": 2, "shoes": 1, "other": 0,
}


def classify_item_type(title: str) -> str:
    """根据 title 关键词分类单品类型"""
    t = str(title).lower()
    for item_type, pattern in ITEM_TYPE_PATTERNS:
        if re.search(pattern, t):
            return item_type
    return "other"


def load_data() -> pd.DataFrame:
    """加载并预处理 historical_sold.csv，fallback 到 sample_historical.csv"""
    path = os.path.join(BASE_DIR, "historical_sold.csv")
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, "sample_historical.csv")
    df = pd.read_csv(path)
    df = df[df["keyword"].isin(TARGET_KEYWORDS)].copy()
    df["sold_date"] = pd.to_datetime(df["sold_date"], errors="coerce")
    df = df.dropna(subset=["sold_date", "sold_price"])
    df = df.sort_values(["keyword", "sold_date"]).reset_index(drop=True)
    return df


def remove_outliers(df: pd.DataFrame, factor: float = 3.0) -> pd.DataFrame:
    """去掉价格偏离中位数 factor 倍以上的异常值"""
    cleaned = []
    for kw, group in df.groupby("keyword"):
        median_price = group["sold_price"].median()
        mask = (group["sold_price"] >= median_price / factor) & \
               (group["sold_price"] <= median_price * factor)
        kept = group[mask]
        removed = len(group) - len(kept)
        if removed > 0:
            print(f"  {kw}: removed {removed} outliers (median=${median_price:.0f})")
        cleaned.append(kept)
    return pd.concat(cleaned).reset_index(drop=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """特征工程：时间特征 + condition 编码 + 滚动均价"""
    df = df.copy()

    # 时间特征
    df["week_of_year"] = df["sold_date"].dt.isocalendar().week.astype(int)
    df["month"] = df["sold_date"].dt.month
    df["day_of_week"] = df["sold_date"].dt.dayofweek
    df["days_since_start"] = (df["sold_date"] - df["sold_date"].min()).dt.days

    # Condition 编码
    df["condition_code"] = df["condition"].map(CONDITION_MAP).fillna(2)

    # Followers
    df["followers"] = df["followers"].fillna(0).astype(int)

    # Item Type（基于 title 分类）
    df["item_type"] = df["title"].apply(classify_item_type)
    df["item_type_code"] = df["item_type"].map(ITEM_TYPE_MAP).fillna(0).astype(int)

    # 滚动均价（按单品分组，按时间排序后计算）
    for window in [7, 14, 30]:
        col_name = f"rolling_avg_{window}d"
        df[col_name] = np.nan
        for kw in df["keyword"].unique():
            mask = df["keyword"] == kw
            kw_df = df.loc[mask].copy()
            rolling_vals = []
            for idx, row in kw_df.iterrows():
                cutoff = row["sold_date"] - pd.Timedelta(days=window)
                past = kw_df[(kw_df["sold_date"] >= cutoff) & (kw_df["sold_date"] < row["sold_date"])]
                rolling_vals.append(past["sold_price"].mean() if len(past) > 0 else np.nan)
            df.loc[mask, col_name] = rolling_vals

    # 用全局中位数填充滚动均价的 NaN（前几条没有历史）
    for window in [7, 14, 30]:
        col = f"rolling_avg_{window}d"
        for kw in df["keyword"].unique():
            mask = df["keyword"] == kw
            median_val = df.loc[mask, "sold_price"].median()
            df.loc[mask, col] = df.loc[mask, col].fillna(median_val)

    return df


FEATURE_COLS = [
    "week_of_year", "month", "day_of_week", "days_since_start",
    "condition_code", "followers", "item_type_code",
    "rolling_avg_7d", "rolling_avg_14d", "rolling_avg_30d",
]


def train_and_evaluate(df: pd.DataFrame) -> list:
    """
    按单品训练模型，时间序列划分（前 80% 训练，后 20% 测试）
    返回每个单品的结果 dict 列表
    """
    results = []

    for kw in TARGET_KEYWORDS:
        kw_df = df[df["keyword"] == kw].copy()
        if len(kw_df) < 10:
            print(f"  Skipping {kw}: only {len(kw_df)} records")
            continue

        # 时间序列拆分
        split_idx = int(len(kw_df) * 0.8)
        train = kw_df.iloc[:split_idx]
        test = kw_df.iloc[split_idx:]

        X_train = train[FEATURE_COLS].values
        y_train = train["sold_price"].values
        X_test = test[FEATURE_COLS].values
        y_test = test["sold_price"].values

        # --- Linear Regression ---
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        lr_pred_test = lr.predict(X_test)
        lr_pred_all = lr.predict(kw_df[FEATURE_COLS].values)
        lr_mae = mean_absolute_error(y_test, lr_pred_test)
        lr_rmse = np.sqrt(mean_squared_error(y_test, lr_pred_test))

        result = {
            "keyword": kw,
            "n_records": len(kw_df),
            "train_size": len(train),
            "test_size": len(test),
            "lr_mae": lr_mae,
            "lr_rmse": lr_rmse,
            "lr_model": lr,
            "lr_pred_all": lr_pred_all,
        }

        # --- Cross-Validation (3-fold time-series) ---
        tscv = TimeSeriesSplit(n_splits=3)
        lr_cv_scores = cross_val_score(
            LinearRegression(), X_train, y_train,
            cv=tscv, scoring="neg_mean_absolute_error",
        )
        result["lr_cv_mae"] = -lr_cv_scores.mean()

        # --- XGBoost (conservative params to reduce overfitting) ---
        if HAS_XGB:
            xgb = XGBRegressor(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                min_child_weight=5,
                random_state=42,
            )
            xgb.fit(X_train, y_train)
            xgb_pred_test = xgb.predict(X_test)
            xgb_pred_all = xgb.predict(kw_df[FEATURE_COLS].values)
            xgb_mae = mean_absolute_error(y_test, xgb_pred_test)
            xgb_rmse = np.sqrt(mean_squared_error(y_test, xgb_pred_test))

            xgb_cv_scores = cross_val_score(
                XGBRegressor(
                    n_estimators=50, max_depth=3,
                    learning_rate=0.1, min_child_weight=5, random_state=42,
                ),
                X_train, y_train,
                cv=tscv, scoring="neg_mean_absolute_error",
            )

            result["xgb_mae"] = xgb_mae
            result["xgb_rmse"] = xgb_rmse
            result["xgb_model"] = xgb
            result["xgb_pred_all"] = xgb_pred_all
            result["xgb_cv_mae"] = -xgb_cv_scores.mean()

        # --- 价格趋势判断 ---
        recent_30d = kw_df[kw_df["sold_date"] >= kw_df["sold_date"].max() - pd.Timedelta(days=30)]
        avg_30d = recent_30d["sold_price"].mean()

        # --- 按 item_type 分别预测 ---
        best_model = xgb if HAS_XGB else lr
        latest_row = kw_df[FEATURE_COLS].iloc[-1:].copy()
        type_col_idx = FEATURE_COLS.index("item_type_code")

        type_predictions = {}
        for itype, icode in ITEM_TYPE_MAP.items():
            type_count = (kw_df["item_type"] == itype).sum()
            if type_count == 0:
                continue
            row = latest_row.copy()
            row.iloc[0, type_col_idx] = icode
            pred = float(best_model.predict(row.values)[0])
            type_median = kw_df.loc[kw_df["item_type"] == itype, "sold_price"].median()
            type_predictions[itype] = {
                "predicted": pred,
                "median": type_median,
                "count": type_count,
                "min": float(kw_df.loc[kw_df["item_type"] == itype, "sold_price"].min()),
                "max": float(kw_df.loc[kw_df["item_type"] == itype, "sold_price"].max()),
            }

        # 整体预测价 = 按各 type 数量加权平均
        total_count = sum(v["count"] for v in type_predictions.values())
        predicted_price = sum(
            v["predicted"] * v["count"] / total_count
            for v in type_predictions.values()
        )

        # 趋势：对比预测价 vs 30天均价
        pct_change = (predicted_price - avg_30d) / avg_30d * 100
        if pct_change > 5:
            trend = "Rising"
        elif pct_change < -5:
            trend = "Declining"
        else:
            trend = "Stable"

        result["avg_30d"] = avg_30d
        result["predicted_price"] = predicted_price
        result["trend"] = trend
        result["pct_change"] = pct_change
        result["type_predictions"] = type_predictions
        result["dates"] = kw_df["sold_date"].values
        result["actuals"] = kw_df["sold_price"].values

        results.append(result)
        cv_info = f", LR CV=${result['lr_cv_mae']:.0f}"
        if HAS_XGB:
            cv_info += f", XGB CV=${result['xgb_cv_mae']:.0f}"
        print(f"  {kw}: LR MAE=${lr_mae:.0f}" +
              (f", XGB MAE=${xgb_mae:.0f}" if HAS_XGB else "") +
              cv_info +
              f" | Predicted=${predicted_price:.0f}, 30d Avg=${avg_30d:.0f}, Trend={trend}")

    return results


def build_summary_table(results: list) -> pd.DataFrame:
    """生成 summary 表"""
    rows = []
    for r in results:
        row = {
            "Item": r["keyword"],
            "Records": r["n_records"],
            "LR MAE ($)": round(r["lr_mae"], 1),
            "LR RMSE ($)": round(r["lr_rmse"], 1),
            "Predicted Price ($)": round(r["predicted_price"], 0),
            "30-Day Avg ($)": round(r["avg_30d"], 0),
            "Trend": r["trend"],
            "Change (%)": round(r["pct_change"], 1),
        }
        row["LR CV MAE ($)"] = round(r.get("lr_cv_mae", r["lr_mae"]), 1)
        if "xgb_mae" in r:
            row["XGB MAE ($)"] = round(r["xgb_mae"], 1)
            row["XGB RMSE ($)"] = round(r["xgb_rmse"], 1)
            row["XGB CV MAE ($)"] = round(r.get("xgb_cv_mae", r["xgb_mae"]), 1)
        rows.append(row)

    cols = ["Item", "Records", "LR MAE ($)", "LR RMSE ($)", "LR CV MAE ($)"]
    if "xgb_mae" in results[0]:
        cols += ["XGB MAE ($)", "XGB RMSE ($)", "XGB CV MAE ($)"]
    cols += ["Predicted Price ($)", "30-Day Avg ($)", "Trend", "Change (%)"]

    return pd.DataFrame(rows)[cols]


def run():
    """完整流程"""
    print("1. Loading data...")
    df = load_data()
    print(f"   {len(df)} records for {df['keyword'].nunique()} items\n")

    print("2. Removing outliers...")
    df = remove_outliers(df)
    print(f"   {len(df)} records after cleanup\n")

    print("3. Building features...")
    df = build_features(df)
    print(f"   Features: {FEATURE_COLS}\n")

    print("4. Training models...")
    results = train_and_evaluate(df)

    print("\n5. Summary:")
    summary = build_summary_table(results)
    print(summary.to_string(index=False))

    return results, df, summary


if __name__ == "__main__":
    run()
