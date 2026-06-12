# legacy/ — 已退役的旧管道(仅存档,勿在新代码中 import)

| 文件 | 原职责 | 被什么替代 |
|---|---|---|
| `grailed_scraper.py` | 关键词搜索抓样本 + CSV | `collectors/grailed.py`(品牌级全量→SQLite);agent 的即席搜索 → `collectors/grailed_search.py` |
| `historical_scraper.py` | 180 天已售 CSV | `run_collect.py` 的 sold 时间窗回填 |
| `run_weekly.py` | 旧周管道编排 | `run_collect.py` + `scorecard.py`(读库版) |
| `item_analysis.py` | 一次性分析脚本 | — |
| `weekly_update.sh` / `daily_update.sh` | 本地 cron(从未生效) | `.github/workflows/weekly_collect.yml` |

旧 CSV 数据已迁入 `data/market.db`(见 `scripts/migrate_csv.py`),原始文件存放于 `data/legacy_csv/`。
