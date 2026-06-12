"""
SQLite 存储层 — 市场数据的唯一事实来源(data/market.db)

设计要点
  · 快照差分而非全量快照:listings 主表一条 listing 一行,
    价格/收藏数发生【变化】才往 listing_events 追加一行 → 体积常年百 MB 内
  · 消失检测:每轮采集后 last_seen 未刷新的 listing 标记 is_active=0,
    "下架 ≈ 售出/删除",由此获得不依赖平台 sold 索引的自有流速信号
  · 质量门禁:pipeline_runs 记录每次运行;本次抓取量比上次成功运行
    暴跌超过阈值 → 拒绝落盘,防止把残数据写进库

表结构
  listings        在售主表 (source, listing_id) 主键
  listing_events  变动事件 (source, listing_id, event_date) 主键
  sold_records    已售成交 (source, listing_id) 主键,不可变
  pipeline_runs   采集运行元数据
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "market.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    source           TEXT NOT NULL,
    listing_id       TEXT NOT NULL,
    brand            TEXT NOT NULL,
    title            TEXT,
    category         TEXT,
    item_type        TEXT,
    series           TEXT,
    condition        TEXT,
    size             TEXT,
    seller_location  TEXT,
    currency         TEXT DEFAULT 'USD',
    price_usd        REAL,
    hearts           INTEGER,
    heat_f           REAL,
    url              TEXT,
    created_at       TEXT,
    first_seen       TEXT NOT NULL,
    last_seen        TEXT NOT NULL,
    is_active        INTEGER DEFAULT 1,
    suspect_mislabel INTEGER DEFAULT 0,
    PRIMARY KEY (source, listing_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_brand  ON listings (brand, is_active);

CREATE TABLE IF NOT EXISTS listing_events (
    source     TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    event_date TEXT NOT NULL,
    price_usd  REAL,
    hearts     INTEGER,
    PRIMARY KEY (source, listing_id, event_date)
);

CREATE TABLE IF NOT EXISTS sold_records (
    source            TEXT NOT NULL,
    listing_id        TEXT NOT NULL,
    brand             TEXT NOT NULL,
    title             TEXT,
    category          TEXT,
    item_type         TEXT,
    series            TEXT,
    condition         TEXT,
    size              TEXT,
    seller_location   TEXT,
    sold_price_usd    REAL,
    price_includes_shipping INTEGER,
    hearts            INTEGER,
    created_at        TEXT,
    sold_at           TEXT,
    days_to_sell      REAL,
    suspect_mislabel  INTEGER DEFAULT 0,
    fetch_date        TEXT,
    PRIMARY KEY (source, listing_id)
);
CREATE INDEX IF NOT EXISTS idx_sold_brand ON sold_records (brand, sold_at);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    finished_at  TEXT,
    source       TEXT,
    brand        TEXT,
    kind         TEXT,              -- 'listings' / 'sold'
    rows_fetched INTEGER,
    rows_written INTEGER,
    requests     INTEGER,
    errors       INTEGER,
    status       TEXT,              -- 'ok' / 'failed' / 'rejected_by_gate'
    note         TEXT
);

CREATE TABLE IF NOT EXISTS scorecard (
    keyword               TEXT NOT NULL,
    brand                 TEXT NOT NULL,
    series                TEXT,
    supply_count          INTEGER,
    demand_count_30d      INTEGER,
    supply_demand_ratio   REAL,
    supply_demand_score   REAL,
    velocity_30d          INTEGER,
    velocity_score        REAL,
    avg_followers         REAL,
    grailed_hype_score    REAL,
    price_recent          REAL,
    price_prior           REAL,
    price_momentum        REAL,
    price_momentum_score  REAL,
    momentum_insufficient INTEGER DEFAULT 0,
    total_score           REAL,
    rank                  INTEGER,
    calc_date             TEXT NOT NULL,
    PRIMARY KEY (keyword, calc_date)   -- 每日快照保留历史,供回测与动量
);

-- 品牌池漏斗 L1:全平台热度时间序列(discovery 扫描 + 试用期浅采集共用)
CREATE TABLE IF NOT EXISTS brand_heat (
    brand          TEXT NOT NULL,
    scan_date      TEXT NOT NULL,
    source         TEXT NOT NULL DEFAULT 'discovery',  -- 'discovery' / 'probe'
    listing_count  INTEGER,        -- discovery: 热门榜出现次数
    avg_hearts     REAL,
    median_price   REAL,
    supply_total   INTEGER,        -- probe: 平台在售总量
    demand_30d     INTEGER,        -- probe: 30 天成交总量
    PRIMARY KEY (brand, scan_date, source)
);

-- 品牌池漏斗 L2:候选品牌(提名→试用→晋升/淘汰)
CREATE TABLE IF NOT EXISTS candidates (
    brand        TEXT PRIMARY KEY,
    facet_name   TEXT,
    nominated_at TEXT,
    status       TEXT DEFAULT 'probation',   -- probation / ready / rejected
    last_check   TEXT,
    note         TEXT
);
"""


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    """打开(必要时初始化)数据库。"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    # 轻量迁移:老库的 sold_records 补 hearts 列(新库由 schema 创建)
    try:
        conn.execute("ALTER TABLE sold_records ADD COLUMN hearts INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 列已存在
    return conn


# ════════════════════════════════════════════════════════════════
# 写入
# ════════════════════════════════════════════════════════════════

def upsert_listings(conn: sqlite3.Connection, rows: list[dict], fetch_date: str) -> tuple[int, int]:
    """
    写入一批在售 listing。
    新 listing → INSERT + 一条 event;
    已有 listing → 刷新 last_seen/is_active/当前值,价格或收藏数变了才追加 event。
    返回 (新增数, 变动数)。
    """
    cur = conn.cursor()
    n_new = n_changed = 0

    for r in rows:
        prev = cur.execute(
            "SELECT price_usd, hearts FROM listings WHERE source=? AND listing_id=?",
            (r["source"], r["listing_id"]),
        ).fetchone()

        if prev is None:
            cur.execute(
                """INSERT INTO listings
                   (source, listing_id, brand, title, category, item_type, series,
                    condition, size, seller_location, currency, price_usd, hearts,
                    heat_f, url, created_at, first_seen, last_seen, is_active,
                    suspect_mislabel)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                (r["source"], r["listing_id"], r["brand"], r.get("title"),
                 r.get("category"), r.get("item_type"), r.get("series"),
                 r.get("condition"), r.get("size"), r.get("seller_location"),
                 r.get("currency", "USD"), r.get("price_usd"), r.get("hearts"),
                 r.get("heat_f"), r.get("url"), r.get("created_at"),
                 fetch_date, fetch_date, r.get("suspect_mislabel", 0)),
            )
            n_new += 1
            changed = True
        else:
            changed = (prev[0] != r.get("price_usd")) or (prev[1] != r.get("hearts"))
            if changed:
                n_changed += 1
            cur.execute(
                """UPDATE listings SET last_seen=?, is_active=1, price_usd=?,
                       hearts=?, heat_f=?, item_type=?, series=?,
                       suspect_mislabel=?
                   WHERE source=? AND listing_id=?""",
                (fetch_date, r.get("price_usd"), r.get("hearts"), r.get("heat_f"),
                 r.get("item_type"), r.get("series"), r.get("suspect_mislabel", 0),
                 r["source"], r["listing_id"]),
            )

        if changed:
            cur.execute(
                """INSERT OR REPLACE INTO listing_events
                   (source, listing_id, event_date, price_usd, hearts)
                   VALUES (?,?,?,?,?)""",
                (r["source"], r["listing_id"], fetch_date,
                 r.get("price_usd"), r.get("hearts")),
            )

    conn.commit()
    return n_new, n_changed


def mark_delisted(conn: sqlite3.Connection, source: str, brand: str, fetch_date: str) -> int:
    """本轮没出现的 listing 标记下架(≈售出/删除信号)。返回标记数。"""
    cur = conn.execute(
        """UPDATE listings SET is_active=0
           WHERE source=? AND brand=? AND is_active=1 AND last_seen < ?""",
        (source, brand, fetch_date),
    )
    conn.commit()
    return cur.rowcount


def insert_sold(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """写入已售记录(不可变,重复忽略)。返回实际新增数。"""
    cur = conn.cursor()
    n = 0
    for r in rows:
        cur.execute(
            """INSERT OR IGNORE INTO sold_records
               (source, listing_id, brand, title, category, item_type, series,
                condition, size, seller_location, sold_price_usd,
                price_includes_shipping, hearts, created_at, sold_at,
                days_to_sell, suspect_mislabel, fetch_date)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["source"], r["listing_id"], r["brand"], r.get("title"),
             r.get("category"), r.get("item_type"), r.get("series"),
             r.get("condition"), r.get("size"), r.get("seller_location"),
             r.get("sold_price_usd"), r.get("price_includes_shipping"),
             r.get("hearts"), r.get("created_at"), r.get("sold_at"),
             r.get("days_to_sell"), r.get("suspect_mislabel", 0),
             r.get("fetch_date")),
        )
        n += cur.rowcount
    conn.commit()
    return n


# ════════════════════════════════════════════════════════════════
# 质量门禁 + 运行记录
# ════════════════════════════════════════════════════════════════

def gate_check(conn: sqlite3.Connection, source: str, brand: str, kind: str,
               current_count: int, threshold: float = 0.5) -> tuple[bool, int | None]:
    """
    与上次【成功】运行的抓取量对比。
    暴跌超过 threshold(默认 50%)→ 判定本次采集异常,拒绝落盘。
    首次运行(无历史)直接放行。返回 (是否通过, 上次数量)。
    """
    row = conn.execute(
        """SELECT rows_fetched FROM pipeline_runs
           WHERE source=? AND brand=? AND kind=? AND status='ok'
           ORDER BY run_id DESC LIMIT 1""",
        (source, brand, kind),
    ).fetchone()
    if row is None or row[0] in (None, 0):
        return True, None
    prev = row[0]
    return current_count >= prev * threshold, prev


def record_run(conn: sqlite3.Connection, *, source: str, brand: str, kind: str,
               started_at: str, rows_fetched: int, rows_written: int,
               requests: int, errors: int, status: str, note: str = "") -> None:
    conn.execute(
        """INSERT INTO pipeline_runs
           (started_at, finished_at, source, brand, kind, rows_fetched,
            rows_written, requests, errors, status, note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (started_at, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         source, brand, kind, rows_fetched, rows_written, requests,
         errors, status, note),
    )
    conn.commit()


def upsert_scorecard(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """写入/覆盖 scorecard 表。"""
    cur = conn.cursor()
    for r in rows:
        cur.execute(
            """INSERT OR REPLACE INTO scorecard
               (keyword, brand, series, supply_count, demand_count_30d,
                supply_demand_ratio, supply_demand_score, velocity_30d,
                velocity_score, avg_followers, grailed_hype_score,
                price_recent, price_prior, price_momentum, price_momentum_score,
                momentum_insufficient, total_score, rank, calc_date)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["keyword"], r["brand"], r.get("series"),
                r.get("supply_count"), r.get("demand_count_30d"),
                r.get("supply_demand_ratio"), r.get("supply_demand_score"),
                r.get("velocity_30d"), r.get("velocity_score"),
                r.get("avg_followers"), r.get("grailed_hype_score"),
                r.get("price_recent"), r.get("price_prior"),
                r.get("price_momentum"), r.get("price_momentum_score"),
                r.get("momentum_insufficient", 0),
                r.get("total_score"), r.get("rank"), r["calc_date"],
            ),
        )
    conn.commit()
