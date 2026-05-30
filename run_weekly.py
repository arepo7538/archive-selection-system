"""
每周执行入口
流程：
  1. （可选）重新跑 discovery，发现市场新热点
  2. 从 discovery 结果自动注入高热度新品牌到关键词列表
  3. 用合并后的关键词列表采集 Grailed 数据
  4. 生成稀缺度评分卡

用法
----
# 仅用现有 discovery.csv（上次已跑过）
python run_weekly.py

# 先重新扫描市场再跑全流程
python run_weekly.py --with-discovery
"""

import sys
import grailed_scraper
import scorecard

# ── 是否先重跑 discovery ──────────────────────────────────────────
WITH_DISCOVERY = "--with-discovery" in sys.argv

if WITH_DISCOVERY:
    print("【Step 0】重新扫描市场热度（discovery）...")
    import discovery as _disc
    _disc.run()
    print()

# ── 从 discovery 结果注入候选新品牌 ───────────────────────────────
print("【Step 1/3】读取 discovery 候选品牌...")
try:
    from discovery import get_candidate_keywords
    new_kws = get_candidate_keywords(top_n=5, min_count=3)
except Exception as e:
    print(f"  ⚠️  读取失败：{e}")
    new_kws = []

if new_kws:
    print(f"  ✅ 发现 {len(new_kws)} 个新品牌，自动加入本周采集：")
    for kw in new_kws:
        print(f"     + {kw}")
    grailed_scraper.KEYWORDS = grailed_scraper.KEYWORDS + new_kws
else:
    print("  （无新品牌，仅用固定关键词列表）")

print(f"\n  本周共采集 {len(grailed_scraper.KEYWORDS)} 个关键词：")
for kw in grailed_scraper.KEYWORDS:
    print(f"     · {kw}")

# ── 采集 + 评分 ───────────────────────────────────────────────────
print("\n【Step 2/3】采集 Grailed 数据...")
grailed_scraper.run()

print("\n【Step 3/3】生成稀缺度评分卡...")
scorecard.build_scorecard()

print("\n✅ 本周数据更新完成！查看 scorecard.csv 获取最新排行。")
