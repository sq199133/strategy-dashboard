# -*- coding: utf-8 -*-
"""
RSRS策略引擎 — 每日输出脚本
============================
由cron定时调度，每日收盘后生成JSON供下游Agent读取。

用法：
  python rsrs_daily_output.py
  python rsrs_daily_output.py --portfolio default --json D:\QClaw_Trading\RSRS\signals\latest.json

下游Agent调用：
  import json
  with open('D:\\QClaw_Trading\\RSRS\\signals\\latest.json') as f:
      signal = json.load(f)
  z = signal['rsrs']['zscore']
"""

import os, sys, json, argparse
from datetime import datetime

# 确保能找到 rsrs_engine.py
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_engine import RSRSStrategy

OUTPUT_DIR = r'D:\QClaw_Trading\RSRS\signals'


def main():
    parser = argparse.ArgumentParser(description='RSRS每日信号输出')
    parser.add_argument('--portfolio', default='default',
                        help='ETF池: default/wide')
    parser.add_argument('--n', type=int, default=18)
    parser.add_argument('--m', type=int, default=1200)
    parser.add_argument('--buy', type=float, default=0.7)
    parser.add_argument('--sell', type=float, default=-1.0)
    parser.add_argument('--rb', type=int, default=42)
    parser.add_argument('--top', type=int, default=1)
    parser.add_argument('--json', default=None,
                        help='输出JSON文件路径')
    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 运行引擎
    print(f'[RSRS每日输出] {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'池: {args.portfolio}')

    strat = RSRSStrategy(
        n=args.n, m=args.m,
        buy_thr=args.buy, sell_thr=args.sell,
        pool=args.portfolio
    )
    result = strat.run(rebalance_days=args.rb, top_n=args.top)

    # 输出路径
    json_path = args.json or os.path.join(OUTPUT_DIR, 'latest.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'信号已写入: {json_path}')

    # 同时写一份带日期的归档
    today = datetime.now().strftime('%Y%m%d')
    archive_path = os.path.join(OUTPUT_DIR, f'signal_{today}.json')
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'归档已写入: {archive_path}')

    # 打印摘要
    print('\n--- 信号摘要 ---')
    print(f'RSRS: Z={result["rsrs"]["zscore"]} ({result["rsrs"]["signal_text"]})')
    top = result['momentum']['c63_top']
    top_name = top[0]['name'] if top else '无'
    top_score = top[0]['score'] if top else 'N/A'
    print(f'动量Top1: {top_name} score={top_score}')
    print(f'仓位: {result["portfolio"]["total_position"]:.1%}')
    print(f'建议: {result["advice"]}')


if __name__ == '__main__':
    main()
