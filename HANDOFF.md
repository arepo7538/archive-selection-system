# HANDOFF — 执行端交接文档

> 本文档是唯一事实来源。按【任务清单】顺序执行,每个任务做完先跑【验收标准】再进行下一个。
> 架构决策已定,不要推翻重设计;有疑问以本文档为准。
> 更新时间:2026-06-12(第二次更新)

## ⚡ 任务状态(2026-06-12 验收)

| 任务 | 状态 | 备注 |
|---|---|---|
| T1 采集完成 | ✅ | 6 品牌 109,499 在售 + 11,318 已售,14/14 运行 ok |
| T2 打分统一+读库 | ✅ | 已验收;scorecard 表主键改为 (keyword, calc_date) 保留每日快照 |
| T3 修 AI 分析页 | ✅ | ReAct 事件流适配完成;另补 data_confidence 推断、热度图改读库 |
| T4 数据年龄警告 | ✅ | dashboard / Selection / Opportunities 已接入 |
| T5 GitHub Actions | ✅ | weekly_collect.yml(注意:runner 无状态,DB 每周重建,接 Supabase 后解决) |
| T6 品牌池自动化 | ✅ | brand_heat 入库 + scripts/universe.py(提名/试用浅采集/晋升/降级)全链路跑通;8 个候选试用中,Kapital/Undercover/If Six Was Nine 指标已达标,14 天试用期满即提示晋升 |
| T7 捡漏雷达页 | ✅ | 已修正:上架天数改用平台 created_at(first_seen 首轮无区分度) |
| price_model 读库 | ✅ | sold_records 7,400 条训练 5 个品牌模型(旧 CSV 仅 205 条);category 粗化 + 预测钳制防 LR 外推溢出;agent 价格工具同步升级(动态品牌匹配) |

**文件结构已重组**:旧管道 → `legacy/`(勿 import);agent 即席搜索 → `collectors/grailed_search.py`;
旧 CSV → `data/legacy_csv/`;演示数据 → `samples/`。清洗规则新增仿款话术过滤(inspired/bootleg/“品牌+style(d)”)。

**Supabase 迁移已完成(2026-06-13)**:
- `lib/db.py` 加了 Postgres 透明兼容层:检测到 `DATABASE_URL` 即走 Supabase,否则本地 SQLite;
  调用方代码零改动(`?`→`%s`、`INSERT OR REPLACE`→`ON CONFLICT` 自动翻译)
- 全部数据已迁入(listings 109,499 / events 110,508 / sold 11,318 等),`scripts/migrate_to_postgres.py` 幂等可重跑
- 用 **6543 事务池端口**(5432 直连是 IPv6,Actions/部分网络连不上)
- dashboard `load_scorecard` 改为优先读 PG scorecard 表;Actions 不再 commit CSV(PG 即持久层)

**剩余待办**:
1. 【需用户操作】GitHub 仓库 Settings → Secrets → Actions 添加 `DATABASE_URL`(6543 端口那串);
   Streamlit Cloud 也加同名 secret —— 两处配好后云端采集+dashboard 才连得上 Supabase
2. 【需用户操作】Supabase 重置数据库密码(密码曾贴进聊天),改完更新 `.env` + 两处 secret
3. AI 分析页端到端实测【需 DEEPSEEK_API_KEY】
4. 2026-06-26 起 universe 试用期满,会对达标品牌打印 watchlist 条目,人工拍板粘贴
5. ⚡ 性能:`upsert_listings` 逐行 SELECT,在 PG 网络环境下 10 万行偏慢(本地 SQLite 无感)。
   若周采集太慢 → 用 `execute_values` + `ON CONFLICT` 批量化(预载 existing dict,去掉逐行往返)

## 0. 项目一句话

Archive 二手服饰(Grailed)量化选品系统:品牌级全量采集 → SQLite → 稀缺度打分 → 价格预测 → Streamlit 多页 dashboard + LangGraph AI agent。当前分支 `feature/react-agent`。

## 1. 刚完成的工作:数据层 v2(已实跑验证,不要改架构)

旧方案用"搜索词"抓样本(漏 95% 数据 + 增量去重 bug 丢价格更新),已重构为:

| 文件 | 职责 | 状态 |
|---|---|---|
| `watchlist.yaml` | 品牌配置:facet 精确名、错标 token、系列正则、超大品牌收窄 | ✅ 6 品牌 |
| `collectors/grailed.py` | 品牌级全量采集:designers.name facet + category/价格两级切片绕 Algolia 1000 条分页上限;已售按 sold_at_i 时间窗递归二分;Session+Retry | ✅ 验证 0 报错 |
| `lib/db.py` | SQLite 存储层:listings(快照差分)/ listing_events(只存变化)/ sold_records / pipeline_runs(质量门禁:抓取量比上次暴跌 50% 拒绝落盘) | ✅ |
| `lib/classify.py` | 本地分类:series(watchlist 正则)+ item_type + suspect_mislabel(标题无品牌词且无季号 → 错标嫌疑,只标记不删除) | ✅ |
| `run_collect.py` | 管道入口:采集→分类→门禁→入库;`--brand` / `--skip-sold` / `--days` | ✅ |
| `scripts/reclassify.py` | 改规则后对库内数据重算分类,**秒级,不重爬** | ✅ |
| `scripts/migrate_csv.py` | 旧 CSV 一次性迁移(已执行,勿重复跑) | ✅ 已执行 |

**已验证的结果(2026-06-12 全 watchlist 实跑,pipeline_runs 14/14 ok)**:

| 品牌 | 在售 | 错标嫌疑率 | 已售(180d, 干净) | 平均在架 | 均价 |
|---|---|---|---|---|---|
| Hysteric Glamour | 58,290 | 54.1%* | 2,380 | 104 天 | $109 |
| Number (N)ine | 13,746 | 19.9% | 2,608 | 82 天 | $171 |
| Vetements | 12,456 | 12.7% | 1,190 | 85 天 | $352 |
| Helmut Lang | 12,314 | 13.6% | 1,125 | 108 天 | $184 |
| Raf Simons | 11,851 | 13.6% | 1,182 | 114 天 | $282 |
| Prada(bowling 收窄) | 247 | 13.8% | 41 | 82 天 | $386 |

合计:listings 109,499 行 / events 110,508 / sold 11,318,库 41.4MB。旧方案同期:已售累计 179 条。

\* Hysteric 54% 错标率是真实现象:Ifsixwasnine/Takaiq/LGB/Metro 7 等品牌卖家批量蹭标签(已抽样确认),
统计务必 `suspect_mislabel=0`。这也说明旧系统的 Hysteric 数据一直被竞品污染。

> T1(确认采集完成)已由本次实跑完成,**Cursor 从 T2 开始执行**。重跑采集是安全的(upsert 幂等)。

## 2. 必须遵守的约定

1. **Python 3.9**(anaconda):新文件如用 `X | None` 类型标注,文件头必须加 `from __future__ import annotations`。
2. 取数主键是品牌,**禁止**退回"搜索词抓样本"模式;系列/单品判定一律在 `lib/classify.py` 本地做。
3. 改分类规则后跑 `python scripts/reclassify.py`,**不要重爬**。
4. `data/` 已 gitignore,**不要提交数据库文件**;旧 CSV 暂保留勿删(dashboard 还在读)。
5. 旧管道文件(`grailed_scraper.py`、`run_weekly.py`、`historical_scraper.py`)暂时保留不动,等任务 T2 完成后再下线。
6. 同一时间只能跑一个 `run_collect.py`(SQLite 写锁)。
7. 读 CSV 用 `encoding="utf-8-sig"`(有 BOM)。
8. 新增依赖先查 anaconda 是否已有;目前只新增了 pyyaml(已在 requirements.txt)。

## 3. 数据库速查(data/market.db)

```sql
-- 表:listings / listing_events / sold_records / pipeline_runs
-- 在售供给:   SELECT COUNT(*) FROM listings WHERE brand=? AND is_active=1 AND suspect_mislabel=0;
-- 30天成交:   SELECT COUNT(*) FROM sold_records WHERE brand=? AND sold_at >= date('now','-30 day') AND suspect_mislabel=0;
-- 在架天数:   SELECT AVG(days_to_sell) FROM sold_records WHERE brand=? AND suspect_mislabel=0;
-- 价格历史:   SELECT event_date, price_usd FROM listing_events WHERE listing_id=? ORDER BY 1;
-- 采集健康:   SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 10;
```

## 4. 任务清单(按顺序执行)

### T1. 确认全量采集完成 ⏱ 5 分钟
- `ps aux | grep run_collect`:若没在跑且 pipeline_runs 里 6 个品牌未齐 → `python run_collect.py` 重跑(幂等)。
- 验收:`SELECT brand, kind, status FROM pipeline_runs` 6 品牌 listings+sold 全 `ok`;6 品牌 `is_active=1` 行数与日志"在售总量"同量级。

### T2. scorecard 切到读库 + 统一打分口径 ⭐ 核心
- 现状问题:`scorecard.py` 用批次内 min-max 相对分(批间不可比、离群值压扁区分度),而 `agent.py:calculate_scarcity_score` 用绝对 log 基线,同一商品两个页面分数不一致。
- 做法:新建 `lib/scoring.py`,以 **agent.py 的绝对基线版本为准**(S/D 35% · Velocity 30% · Hype 25% · Momentum 10%);scorecard.py 改为:从 SQLite 读各品牌指标(供给=活跃 listing 数、30 天成交、平均 hearts、momentum 用 listing_events 的周环比中位价,数据不足时 5.0 并标注),调 lib/scoring.py,结果写 `scorecard` 表 + 兼容导出 `scorecard.csv`(列名不变,dashboard 不用改)。agent.py 的 `calculate_scarcity_score` 改为 import lib/scoring.py(单一事实来源)。
- 打分对象:品牌级 + 有 series 标签的子集(如 Number (N)ine/AW03)各算一行,替代旧的 16 个关键词。
- 验收:`python scorecard.py` 跑通;同一品牌在 scorecard.csv 与 agent 工具输出的 total_score 一致;Selection 页正常渲染。

### T3. 修复 AI 分析页(当前是坏的)
- Bug:`pages/3_AI_Analysis.py:102` `from agent import app` → ImportError(agent.py 已重写为 ReAct,无 `app` 导出)。
- 做法:改用 `from agent import stream_analyze_react`;遍历事件流,事件结构 `{"agent": {...}}` / `{"tools": {"messages": [ToolMessage,...]}}`;按 ToolMessage.name 显示进度(validate_brand → fetch_market_data → calculate_scarcity_score → fetch_celebrity_signal → get_price_prediction),`json.loads(ToolMessage.content)` 解析结果填左侧 Market Data 表;最后一条 AI message 为报告。删除旧 DAG 事件名分支(preprocess/brand_validator/validator/celebrity_signal/score/analyze)。
- 顺带:页面 meta 文案 "Google Trends" → "Wikipedia Pageviews";dashboard.py footer "LangGraph node DAG..." → "ReAct tool-calling"。
- 验收:无 DEEPSEEK_API_KEY 时显示清晰提示不崩;有 key 时输入 "Number Nine AW03" 全流程出报告,Market Data 表有数字。

### T4. Dashboard 数据年龄警告
- dashboard.py + 1_Selection.py 顶部:数据日期(pipeline_runs 最近 ok 的 finished_at)距今 >7 天黄条提醒、>14 天红条。
- 验收:手动改库里日期能触发两档警告。

### T5. GitHub Actions 周采集(替代从未生效的本地 cron)
- `.github/workflows/weekly_collect.yml`:cron 每周一 09:00 UTC+8;steps:checkout → setup-python 3.11 → pip install -r requirements.txt → `python run_collect.py` → `python scorecard.py` → commit scorecard.csv 等派生 CSV(库文件不提交)。失败时 workflow 红灯即报警。
- 注意:Actions 的 runner 无状态,market.db 每次重建(全量采集本来就是幂等的,可接受);scorecard.csv 是 Streamlit Cloud 的数据来源。后续接 Supabase 时再改为写云库。
- 验收:workflow_dispatch 手动触发一次全绿。

### T6. 品牌池自动化 — 三层漏斗(L0 全平台扫描 → L2 试用 → L3 深采集)

> 设计意图:watchlist 不靠人拍脑袋,由数据提名、试用、晋升/降级;人只保留一票否决。

**T6a. discovery 入库(L0→L1)**
- discovery.py 的品牌榜结果写入新表 `brand_heat(brand, scan_date, listing_count, avg_hearts, median_price)`(替代只存 CSV);每天跑(后续进 Actions)。
- 验收:连续两次运行后,`SELECT brand, COUNT(*) FROM brand_heat GROUP BY brand` 有时间序列。

**T6b. 提名 + 试用期浅采集(L1→L2)**
- 新建 `scripts/universe.py`:
  - 提名:`brand_heat` 中连续 ≥3 次上榜、且不在 watchlist 的品牌 → 写入 `candidates(brand, facet_name, nominated_at, status='probation')`;facet 精确名用 Algolia facet 搜索 API 自动验证(参考 collectors/grailed.py 的请求方式)。
  - 浅采集:对 probation 品牌每周只拿 3 个数:在售总数 nb_hits、30 天已售 nb_hits、top100 的 avg hearts/median price,追加进 `brand_heat`。
- 验收:`python scripts/universe.py` 打印候选名单与浅采集指标。

**T6c. 晋升/降级判定(L2→L3)**
- 晋升条件(初始值,做成 universe.py 顶部可调常量):30 天成交 ≥30 且 在售 1,000~60,000 且 中位价 $100~$1,000 且 试用 ≥2 周。
- 满足 → 打印可直接粘贴进 watchlist.yaml 的完整条目(name/grailed_facet/title_tokens 初稿)+ 在 candidates 表标 `status='ready'`。**不自动写 yaml,人工确认后粘贴**(一票否决权)。
- 降级:watchlist 品牌连续 4 周 30 天成交 <10 → 打印降级建议。
- 验收:用一个已知热门品牌(如 Rick Owens)走通全流程到"ready"状态。

### T7. 机会雷达页(新页面,产品杀手锏第一步)
- `pages/4_Opportunities.py`:SQL 筛选库内"捡漏"——价格低于同品牌同品类(suspect_mislabel=0)中位价 30%+、上架 <14 天、hearts 高于品牌 P80;表格列:标题/价格/中位价/折扣%/品类/series/在架天数/**Grailed 链接**(listings.url)。
- 验收:页面可按品牌筛选,点链接能打开真实 listing。

## 5. 已知坑

- Hysteric Glamour 量大(5.8 万),单品牌采集 ~10 分钟,正常。
- 错标率 ~20% 是平台卖家蹭标签所致,属预期;一切统计务必带 `suspect_mislabel=0`。
- Prada 在 watchlist 里被 `grailed_query: "bowling"` 收窄(全量 9.3 万太大),这是配置特性不是 bug。
- `momentum` 在数据积累 <2 周前会是中性 5.0,属预期,UI 标注"数据积累中"。
- 旧 scorecard.csv 里有 5 个已改名关键词的僵尸行,T2 完成后自然消失。
