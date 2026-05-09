"""
每周执行入口
按顺序跑：采集 → 评分卡
"""

import grailed_scraper
import scorecard

if __name__ == "__main__":
    print("【Step 1/2】采集 Grailed 数据...")
    grailed_scraper.run()

    print("\n【Step 2/2】生成稀缺度评分卡...")
    scorecard.build_scorecard()

    print("\n本周数据更新完成！查看 scorecard.csv 获取最新排行。")
