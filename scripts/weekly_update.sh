#!/bin/bash
# ─────────────────────────────────────────────────
# weekly_update.sh  —  每周全流程 + 自动提交
# 流程：discovery → 采集 → 评分 → 历史数据 → git push
# crontab: 0 9 * * 1 /path/to/scripts/weekly_update.sh
# ─────────────────────────────────────────────────

PYTHON="/Users/yulingfeng/opt/anaconda3/bin/python"
PROJECT="/Users/yulingfeng/Desktop/apply_for_job/个人创业量化"
LOG="$PROJECT/logs/weekly_$(date +%Y-%m-%d).log"

mkdir -p "$PROJECT/logs"

echo "=============================" >> "$LOG"
echo "  Weekly Pipeline 开始" >> "$LOG"
echo "  $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
echo "=============================" >> "$LOG"

cd "$PROJECT" || exit 1

# 1. 全流程（含重新 discovery）
echo "[1/3] 运行 run_weekly.py --with-discovery ..." >> "$LOG"
$PYTHON run_weekly.py --with-discovery >> "$LOG" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ run_weekly.py 运行失败，终止" >> "$LOG"
    exit 1
fi

# 2. 追加历史成交数据
echo "[2/3] 运行 historical_scraper.py ..." >> "$LOG"
$PYTHON historical_scraper.py >> "$LOG" 2>&1

# 3. Git commit + push（提交所有数据文件）
echo "[3/3] 提交并推送..." >> "$LOG"
git add \
    discovery.csv discovery_raw.csv \
    grailed_listings.csv grailed_sold.csv grailed_totals.csv \
    scorecard.csv historical_sold.csv \
    >> "$LOG" 2>&1

git diff --cached --quiet && echo "  无变化，跳过 commit" >> "$LOG" && exit 0

git commit -m "chore(data): weekly pipeline update $(date +%Y-%m-%d)" >> "$LOG" 2>&1
git push origin HEAD >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 推送成功" >> "$LOG"
else
    echo "❌ 推送失败，请检查 GitHub 权限" >> "$LOG"
fi

echo "完成 $(date '+%H:%M:%S')" >> "$LOG"
