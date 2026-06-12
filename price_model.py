"""
Price Prediction Model — Pooled / Unified Architecture
=======================================================
所有关键词数据合并成一张表，训练一个统一的 LR + XGBoost。

关键改动（对比旧版单品分别建模）：
  - keyword 做 LabelEncoder，让模型学品牌价格基线
  - category 做 one-hot
  - condition 做有序编码（4档）
  - followers 做 log1p 变换
  - 新增：days_listed（上架到成交天数）、sold_month、sold_dayofweek
  - 目标变量改为 log(sold_price)，输出时 exp() 还原
  - 按 sold_date 时间顺序全局 80/20 切分

公开接口（与 lib/data.py / agent.py 兼容）：
  load_data()        → DataFrame（216 行）
  remove_outliers()  → 清洗后 DataFrame
  build_features()   → 特征工程后 DataFrame
  train_and_evaluate() → list of per-keyword result dicts
  build_summary_table() → summary DataFrame

CLI: python price_model.py
"""

import os
import re
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder
from typing import Optional

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("Warning: xgboost not installed — XGBoost model skipped.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 跟踪哪些关键词有足够历史数据 ──────────────────────────────────
TARGET_KEYWORDS = [
    "Number Nine AW03",
    "Number Nine AW09",
    "Vetements oversized hoodie",
    "Helmut Lang SS99",
    "Prada bowling shirt",
]

# ── 成色有序编码（worn=1 最差 → new=4 最好）─────────────────────
CONDITION_MAP = {
    "is_worn":         1,
    "is_used":         2,
    "is_gently_used":  3,
    "is_new":          4,
}

# ── 单品类型（按 title 关键词匹配，用于预测明细）─────────────────
ITEM_TYPE_PATTERNS = [
    ("jacket", r"jacket|bomber|varsity|blazer|ma-1|flight|coat"),
    ("pants",  r"pants|jeans|denim(?!.*jacket)|trouser|bondage.*jean"),
    ("hoodie", r"hoodie|hoody|sweatshirt"),
    ("tee",    r"t-?shirt|tee\b|tshirt"),
    ("shirt",  r"shirt(?!.*t-shirt)"),
    ("shoes",  r"shoe|sneaker|converse|boot"),
]

ITEM_TYPE_MAP = {
    "jacket": 6, "pants": 5, "hoodie": 4,
    "shirt": 3, "tee": 2, "shoes": 1, "other": 0,
}


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

def classify_item_type(title: str) -> str:
    """title 关键词匹配 → 单品类型字符串"""
    t = str(title).lower()
    for item_type, pattern in ITEM_TYPE_PATTERNS:
        if re.search(pattern, t):
            return item_type
    return "other"


def parse_season_year(title: str) -> tuple:
    """
    从 title 中正则解析年份/季节信息，返回 (year: float, has_year: int)。

    匹配模式（优先级从高到低）：
      1. 季节码 + 4位年份  "AW2003"  "SS2005"  "FW1999"
      2. 季节码 + 2位年份  "AW03"    "SS99"    "FW '03"
      3. 撇号  + 2位年份  "'03"     "'99"
      4. 独立4位年份       "2003"    "1985"   （限 1980-2029）

    2位年份转换规则：00-29 → 2000-2029；30-99 → 1930-1999
    解析失败返回 (nan, 0)，调用方用中位数填充 nan。
    """
    t = str(title)

    # 1. 季节码 + 4位年份（AW2003, SS2005, FW1999, RE2010, SP2000）
    m = re.search(r'\b(?:AW|SS|FW|FA|RE|SP)\s*(\d{4})\b', t, re.IGNORECASE)
    if m:
        return float(m.group(1)), 1

    # 2. 季节码 + 2位年份，支持中间有空格或撇号（AW03, SS '99, FW03）
    m = re.search(r'\b(?:AW|SS|FW|FA|RE|SP)\s*\x27?\s*(\d{2})\b', t, re.IGNORECASE)
    if m:
        yy = int(m.group(1))
        year = 2000 + yy if yy <= 29 else 1900 + yy
        return float(year), 1

    # 3. 撇号 + 2位年份（'03, '99）
    m = re.search(r"[\x27\x60](\d{2})\b", t)  # \x27=apostrophe, \x60=backtick
    if m:
        yy = int(m.group(1))
        year = 2000 + yy if yy <= 29 else 1900 + yy
        return float(year), 1

    # 4. 独立4位年份（1980-2029 范围，避免匹配价格/尺码等数字）
    m = re.search(r'\b(19[89]\d|20[012]\d)\b', t)
    if m:
        return float(m.group(1)), 1

    return float("nan"), 0


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error（跳过真实值为 0 的行）"""
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


# ══════════════════════════════════════════════════════════════════
# 1. load_data
# ══════════════════════════════════════════════════════════════════

def load_data() -> pd.DataFrame:
    """
    读取 historical_sold.csv（或 sample_historical.csv 兜底）。
    只保留 TARGET_KEYWORDS 中的关键词，按 sold_date 排序。
    """
    path = os.path.join(BASE_DIR, "data", "legacy_csv", "historical_sold.csv")
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, "samples", "sample_historical.csv")
    df = pd.read_csv(path)
    df = df[df["keyword"].isin(TARGET_KEYWORDS)].copy()
    df["sold_date"] = pd.to_datetime(df["sold_date"], errors="coerce")
    df = df.dropna(subset=["sold_date", "sold_price"])
    df = df.sort_values("sold_date").reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════
# 2. remove_outliers
# ══════════════════════════════════════════════════════════════════

def remove_outliers(df: pd.DataFrame, factor: float = 3.0) -> pd.DataFrame:
    """
    按关键词分组，去掉偏离中位数 factor 倍以上的价格异常值。
    清洗后仍按 sold_date 全局排序，保持时序连续性。
    """
    cleaned = []
    for kw, group in df.groupby("keyword"):
        median_price = group["sold_price"].median()
        mask = (
            (group["sold_price"] >= median_price / factor) &
            (group["sold_price"] <= median_price * factor)
        )
        kept = group[mask]
        removed = len(group) - len(kept)
        if removed > 0:
            print(f"  {kw}: removed {removed} outliers (median=${median_price:.0f})")
        cleaned.append(kept)
    return pd.concat(cleaned).sort_values("sold_date").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════
# 3. build_features  ← 核心改动
# ══════════════════════════════════════════════════════════════════

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一特征工程（汇总建模版）：

    原始列         处理方式
    ─────────────  ──────────────────────────────────────────────
    keyword        LabelEncoder → keyword_code（品牌价格基线）
    condition      CONDITION_MAP 有序编码 → condition_code
    category       pd.get_dummies one-hot → cat_*
    followers      log1p → log_followers（压制极端值）
    title          classify_item_type → item_type_code（价格分档）
                   parse_season_year  → season_year（年份）+ has_season_year（是否解析到）
    sold_date      月份 → sold_month，星期 → sold_dayofweek
    created_at     (sold_date - created_at).days → days_listed
    sold_price     log → log_price（目标变量，减小右偏）
    """
    df = df.copy()

    # 1. keyword label encoding
    le = LabelEncoder()
    df["keyword_code"] = le.fit_transform(df["keyword"])

    # 2. condition 有序编码（缺失填 is_used=2）
    df["condition_code"] = df["condition"].map(CONDITION_MAP).fillna(2).astype(int)

    # 3. category one-hot（drop_first=False 保留全部，模型可自行处理共线）
    df = pd.get_dummies(df, columns=["category"], prefix="cat", drop_first=False)

    # 4. followers log1p（原始值有 0，log1p 安全）
    df["followers"] = pd.to_numeric(df.get("followers", 0), errors="coerce").fillna(0)
    df["log_followers"] = np.log1p(df["followers"])

    # 5. item_type 有序编码（jacket=6 最贵 → other=0）
    df["item_type"] = df["title"].apply(classify_item_type)
    df["item_type_code"] = df["item_type"].map(ITEM_TYPE_MAP).fillna(0).astype(int)

    # 6. days_listed：上架到成交的天数（衡量"好不好卖"）
    if "created_at" in df.columns:
        # created_at 含时区（ISO "Z"），统一去掉时区再做差
        df["created_at_dt"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True).dt.tz_localize(None)
        days = (df["sold_date"] - df["created_at_dt"]).dt.days
        # 负数（数据质量问题）和缺失值用中位数填充
        days = days.clip(lower=0)
        days = days.fillna(days.median() if days.notna().any() else 30)
        df["days_listed"] = days.astype(int)
    else:
        df["days_listed"] = 30  # 无上架时间时用默认值

    # 7. 成交时间特征
    df["sold_month"]      = df["sold_date"].dt.month        # 1-12
    df["sold_dayofweek"]  = df["sold_date"].dt.dayofweek   # 0=Mon…6=Sun

    # 8. 年份/季节特征：从 title 正则解析 AW03 / SS99 / 2003 等格式
    parsed = df["title"].apply(parse_season_year)
    df["season_year"]     = parsed.apply(lambda x: x[0])   # float，解析失败为 nan
    df["has_season_year"] = parsed.apply(lambda x: x[1])   # 0/1 缺失标记

    # 解析覆盖率统计
    n_parsed = df["has_season_year"].sum()
    n_total  = len(df)
    print(f"  [season_year] parsed {n_parsed}/{n_total} titles "
          f"({n_parsed/n_total*100:.0f}%) — sample: "
          + str(df.loc[df["has_season_year"]==1, ["title","season_year"]]
                  .head(3).values.tolist()))

    # 用各关键词的中位数年份填充解析不到的行（避免跨品牌污染）
    for kw, grp in df.groupby("keyword"):
        med = grp.loc[grp["has_season_year"] == 1, "season_year"].median()
        if pd.isna(med):
            med = 2003.0   # 全组都解析不到时用全局默认值
        mask = (df["keyword"] == kw) & df["season_year"].isna()
        df.loc[mask, "season_year"] = med
    df["season_year"] = df["season_year"].astype(float)

    # 9. 目标变量：log(sold_price)
    df["log_price"] = np.log(df["sold_price"].clip(lower=1).astype(float))

    return df


def _get_feature_cols(df: pd.DataFrame) -> list:
    """
    动态拼接特征列（含 category one-hot 列）。
    固定列顺序：品牌 → 成色 → 收藏 → 类型 → 时间 → 上架天数 → 年份 → category one-hot
    """
    cat_cols = sorted(c for c in df.columns if c.startswith("cat_"))
    return [
        "keyword_code",
        "condition_code",
        "log_followers",
        "item_type_code",
        "sold_month",
        "sold_dayofweek",
        "days_listed",
        "season_year",       # ← 新增：数值年份
        "has_season_year",   # ← 新增：是否解析到年份（0/1 缺失标记）
    ] + cat_cols


# ══════════════════════════════════════════════════════════════════
# 4. train_and_evaluate  ← 汇总建模
# ══════════════════════════════════════════════════════════════════

def train_and_evaluate(df: pd.DataFrame) -> list:
    """
    统一训练 1 个 LR + 1 个 XGBoost（目标：log_price）。

    划分策略：
      - 全量数据按 sold_date 排序
      - 前 80% 为训练集，后 20% 为测试集（时间序列顺序，不随机）

    输出：
      - 控制台打印全局 Train/Test MAE 和 MAPE
      - 控制台打印 XGBoost 特征重要性
      - 返回 per-keyword results list（与 pages/2_Price_Prediction.py 兼容）
    """
    feature_cols = _get_feature_cols(df)

    # ── 全局 80/20 时间顺序切分 ─────────────────────────────────
    df = df.sort_values("sold_date").reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    test_df  = df.iloc[split_idx:].copy()

    X_train = train_df[feature_cols].values
    y_train = train_df["log_price"].values       # log scale
    X_test  = test_df[feature_cols].values
    y_test  = test_df["log_price"].values

    # 评估用原始价格
    y_train_orig = train_df["sold_price"].values.astype(float)
    y_test_orig  = test_df["sold_price"].values.astype(float)

    # ── Linear Regression（基线）────────────────────────────────
    lr = LinearRegression()
    lr.fit(X_train, y_train)

    lr_train_pred = np.exp(lr.predict(X_train))
    lr_test_pred  = np.exp(lr.predict(X_test))
    lr_all_pred   = np.exp(lr.predict(df[feature_cols].values))

    lr_train_mae  = mean_absolute_error(y_train_orig, lr_train_pred)
    lr_test_mae   = mean_absolute_error(y_test_orig,  lr_test_pred)
    lr_train_mape = _mape(y_train_orig, lr_train_pred)
    lr_test_mape  = _mape(y_test_orig,  lr_test_pred)

    lr_train_rmse = np.sqrt(mean_squared_error(y_train_orig, lr_train_pred))
    lr_test_rmse  = np.sqrt(mean_squared_error(y_test_orig,  lr_test_pred))

    print()
    print("=" * 60)
    print("  POOLED MODEL — Linear Regression (baseline)")
    print("=" * 60)
    print(f"  Train  MAE=${lr_train_mae:.0f}  RMSE=${lr_train_rmse:.0f}  MAPE={lr_train_mape:.1f}%")
    print(f"  Test   MAE=${lr_test_mae:.0f}  RMSE=${lr_test_rmse:.0f}  MAPE={lr_test_mape:.1f}%")

    # ── XGBoost ─────────────────────────────────────────────────
    xgb_model    = None
    xgb_all_pred = lr_all_pred       # fallback if no XGBoost
    xgb_test_pred = lr_test_pred
    xgb_test_mae  = lr_test_mae
    xgb_test_rmse = lr_test_rmse
    xgb_test_mape = lr_test_mape

    if HAS_XGB:
        xgb_model = XGBRegressor(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            min_child_weight=5,     # 防止对小样本单品过拟合
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0,
        )
        xgb_model.fit(X_train, y_train)

        xgb_train_pred = np.exp(xgb_model.predict(X_train))
        xgb_test_pred  = np.exp(xgb_model.predict(X_test))
        xgb_all_pred   = np.exp(xgb_model.predict(df[feature_cols].values))

        xgb_train_mae  = mean_absolute_error(y_train_orig, xgb_train_pred)
        xgb_test_mae   = mean_absolute_error(y_test_orig,  xgb_test_pred)
        xgb_train_mape = _mape(y_train_orig, xgb_train_pred)
        xgb_test_mape  = _mape(y_test_orig,  xgb_test_pred)

        xgb_train_rmse = np.sqrt(mean_squared_error(y_train_orig, xgb_train_pred))
        xgb_test_rmse  = np.sqrt(mean_squared_error(y_test_orig,  xgb_test_pred))

        print()
        print("=" * 60)
        print("  POOLED MODEL — XGBoost")
        print("=" * 60)
        print(f"  Train  MAE=${xgb_train_mae:.0f}  RMSE=${xgb_train_rmse:.0f}  MAPE={xgb_train_mape:.1f}%")
        print(f"  Test   MAE=${xgb_test_mae:.0f}  RMSE=${xgb_test_rmse:.0f}  MAPE={xgb_test_mape:.1f}%")

        # 特征重要性
        print()
        print("  XGBoost Feature Importance (gain):")
        print(f"  {'Feature':<25}  Importance")
        print(f"  {'-'*40}")
        fi_pairs = sorted(
            zip(feature_cols, xgb_model.feature_importances_),
            key=lambda x: x[1], reverse=True,
        )
        for fname, fval in fi_pairs:
            bar = "█" * int(fval * 200)
            print(f"  {fname:<25}  {fval:.4f}  {bar}")

    # ── Per-keyword results（dashboard 兼容格式）─────────────────
    print()
    print("=" * 60)
    print("  Per-Keyword Metrics (from unified model)")
    print("=" * 60)

    results = []
    best_model = xgb_model if HAS_XGB and xgb_model is not None else lr

    # boolean masks on df，numpy 形式方便切片
    kw_arr       = df["keyword"].values
    train_kw_arr = train_df["keyword"].values
    test_kw_arr  = test_df["keyword"].values

    for kw in TARGET_KEYWORDS:
        kw_df = df[kw_arr == kw].copy()
        if len(kw_df) < 5:
            print(f"  Skipping {kw}: only {len(kw_df)} records")
            continue

        # 该关键词在训练集里有几条
        kw_train_size = int((train_kw_arr == kw).sum())
        kw_test_mask  = test_kw_arr == kw

        # 全量预测（用于趋势图）
        kw_lr_pred_all  = lr_all_pred[kw_arr == kw]
        kw_xgb_pred_all = xgb_all_pred[kw_arr == kw] if HAS_XGB else kw_lr_pred_all

        # 该关键词在测试集上的 MAE
        kw_test_actual = test_df.loc[kw_test_mask, "sold_price"].values.astype(float)
        if len(kw_test_actual) > 0:
            kw_lr_test_pred  = lr_test_pred[kw_test_mask]
            kw_xgb_test_pred = xgb_test_pred[kw_test_mask] if HAS_XGB else kw_lr_test_pred

            kw_lr_mae  = mean_absolute_error(kw_test_actual, kw_lr_test_pred)
            kw_lr_rmse = np.sqrt(mean_squared_error(kw_test_actual, kw_lr_test_pred))
            kw_xgb_mae  = mean_absolute_error(kw_test_actual, kw_xgb_test_pred) if HAS_XGB else kw_lr_mae
            kw_xgb_rmse = np.sqrt(mean_squared_error(kw_test_actual, kw_xgb_test_pred)) if HAS_XGB else kw_lr_rmse
        else:
            # 该关键词全在训练集（数据少时可能出现），退回全局测试 MAE
            kw_lr_mae = kw_lr_rmse = lr_test_mae
            kw_xgb_mae = kw_xgb_rmse = xgb_test_mae if HAS_XGB else lr_test_mae

        # 30 天均价
        recent_30d = kw_df[
            kw_df["sold_date"] >= kw_df["sold_date"].max() - pd.Timedelta(days=30)
        ]
        avg_30d = float(
            recent_30d["sold_price"].mean() if len(recent_30d) > 0
            else kw_df["sold_price"].mean()
        )

        # 按 item_type 预测细分价格（用最新特征行 + 替换 item_type_code）
        latest_row = kw_df[feature_cols].iloc[-1:].copy()
        type_col_idx = feature_cols.index("item_type_code")

        type_predictions = {}
        for itype, icode in ITEM_TYPE_MAP.items():
            type_count = int((kw_df["item_type"] == itype).sum())
            if type_count == 0:
                continue
            row = latest_row.copy()
            row.iloc[0, type_col_idx] = icode
            pred_log = float(best_model.predict(row.values)[0])
            pred_price = float(np.exp(pred_log))
            subset = kw_df[kw_df["item_type"] == itype]["sold_price"]
            type_predictions[itype] = {
                "predicted": pred_price,
                "median":    float(subset.median()),
                "count":     type_count,
                "min":       float(subset.min()),
                "max":       float(subset.max()),
            }

        # 加权平均预测价（各 type 按数量加权）
        total_count = sum(v["count"] for v in type_predictions.values())
        if total_count > 0:
            predicted_price = sum(
                v["predicted"] * v["count"] / total_count
                for v in type_predictions.values()
            )
        else:
            predicted_price = float(np.exp(best_model.predict(latest_row.values)[0]))

        pct_change = (predicted_price - avg_30d) / avg_30d * 100 if avg_30d else 0.0
        trend = "Rising" if pct_change > 5 else ("Declining" if pct_change < -5 else "Stable")

        print(
            f"  {kw}: "
            f"LR MAE=${kw_lr_mae:.0f}"
            + (f", XGB MAE=${kw_xgb_mae:.0f}" if HAS_XGB else "")
            + f" | Predicted=${predicted_price:.0f}, 30d Avg=${avg_30d:.0f}, Trend={trend}"
        )

        result = {
            # 基础信息
            "keyword":       kw,
            "n_records":     len(kw_df),
            "train_size":    kw_train_size,
            "test_size":     int(kw_test_mask.sum()),

            # LR
            "lr_mae":        kw_lr_mae,
            "lr_rmse":       kw_lr_rmse,
            "lr_cv_mae":     lr_test_mae,    # 全局 test MAE 作为 CV 代理
            "lr_model":      lr,
            "lr_pred_all":   kw_lr_pred_all,

            # 价格 & 趋势
            "avg_30d":          avg_30d,
            "predicted_price":  predicted_price,
            "trend":            trend,
            "pct_change":       pct_change,
            "type_predictions": type_predictions,
            "dates":            kw_df["sold_date"].values,
            "actuals":          kw_df["sold_price"].values,
        }

        if HAS_XGB and xgb_model is not None:
            result["xgb_mae"]      = kw_xgb_mae
            result["xgb_rmse"]     = kw_xgb_rmse
            result["xgb_cv_mae"]   = xgb_test_mae   # 全局 test MAE 作为 CV 代理
            result["xgb_model"]    = xgb_model
            result["xgb_pred_all"] = kw_xgb_pred_all

        results.append(result)

    return results


# ══════════════════════════════════════════════════════════════════
# 5. build_summary_table
# ══════════════════════════════════════════════════════════════════

def build_summary_table(results: list) -> pd.DataFrame:
    """
    将 train_and_evaluate 的结果列表整理成 DataFrame，供 dashboard 展示。
    空列表时返回空表，避免下游 IndexError。
    """
    if not results:
        return pd.DataFrame(columns=[
            "Item", "Records", "LR MAE ($)", "LR RMSE ($)", "LR CV MAE ($)",
            "Predicted Price ($)", "30-Day Avg ($)", "Trend", "Change (%)",
        ])

    rows = []
    for r in results:
        row = {
            "Item":                 r["keyword"],
            "Records":              r["n_records"],
            "LR MAE ($)":           round(r["lr_mae"],  1),
            "LR RMSE ($)":          round(r["lr_rmse"], 1),
            "LR CV MAE ($)":        round(r.get("lr_cv_mae", r["lr_mae"]), 1),
            "Predicted Price ($)":  round(r["predicted_price"], 0),
            "30-Day Avg ($)":       round(r["avg_30d"], 0),
            "Trend":                r["trend"],
            "Change (%)":           round(r["pct_change"], 1),
        }
        if "xgb_mae" in r:
            row["XGB MAE ($)"]    = round(r["xgb_mae"],  1)
            row["XGB RMSE ($)"]   = round(r["xgb_rmse"], 1)
            row["XGB CV MAE ($)"] = round(r.get("xgb_cv_mae", r["xgb_mae"]), 1)
        rows.append(row)

    cols = ["Item", "Records", "LR MAE ($)", "LR RMSE ($)", "LR CV MAE ($)"]
    if "xgb_mae" in results[0]:
        cols += ["XGB MAE ($)", "XGB RMSE ($)", "XGB CV MAE ($)"]
    cols += ["Predicted Price ($)", "30-Day Avg ($)", "Trend", "Change (%)"]

    return pd.DataFrame(rows)[cols]


# ══════════════════════════════════════════════════════════════════
# 6. run  —  完整流程入口
# ══════════════════════════════════════════════════════════════════

def run():
    print("1. Loading data...")
    df = load_data()
    print(f"   {len(df)} records, {df['keyword'].nunique()} keywords\n")

    print("2. Removing outliers...")
    df = remove_outliers(df)
    print(f"   {len(df)} records after cleanup\n")

    print("3. Building features...")
    df = build_features(df)
    feature_cols = _get_feature_cols(df)
    print(f"   {len(feature_cols)} features: {feature_cols}\n")

    print("4. Training pooled models (80/20 chronological split)...")
    results = train_and_evaluate(df)

    print("\n5. Summary table:")
    summary = build_summary_table(results)
    print(summary.to_string(index=False))

    return results, df, summary


if __name__ == "__main__":
    run()
