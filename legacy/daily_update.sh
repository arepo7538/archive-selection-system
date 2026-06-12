#!/bin/bash
# ─────────────────────────────────────────────────
# daily_update.sh  —  每日 Discovery 扫描 + 自动提交
# crontab: 0 8 * * * /path/to/scripts/daily_update.sh
# ─────────────────────────────────────────────────

PYTHON="/Users/yulingfeng/opt/anaconda3/bin/python"
PROJECT="/Users/yulingfeng/Desktop/apply_for_job/个人创业量化"
LOG="$PROJECT/logs/daily_$(date +%Y-%m-%d).log"

mkdir -p "$PROJECT/logs"

echo "=============================" >> "$LOG"
echo "  Daily Discovery 开始" >> "$LOG"
echo "  $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
echo "=============================" >> "$LOG"

cd "$PROJECT" || exit 1

# 1. 跑 discovery
echo "[1/2] 运行 discovery.py ..." >> "$LOG"
$PYTHON discovery.py >> "$LOG" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ discovery.py 运行失败，终止" >> "$LOG"
    exit 1
fi

# 2. Git commit + push
echo "[2/2] 提交并推送..." >> "$LOG"
git add discovery.csv discovery_raw.csv >> "$LOG" 2>&1
git diff --cached --quiet && echo "  无变化，跳过 commit" >> "$LOG" && exit 0

git commit -m "chore(data): daily discovery update $(date +%Y-%m-%d)" >> "$LOG" 2>&1
git push origin HEAD >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 推送成功" >> "$LOG"
else
    echo "❌ 推送失败，请检查 GitHub 权限" >> "$LOG"
fi

echo "完成 $(date '+%H:%M:%S')" >> "$LOG"
