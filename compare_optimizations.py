#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比回测：原版v4.3 vs 优化版（动态仓位+成交量过滤）
"""

import subprocess
import json
import os
import sys
from datetime import datetime

# 配置
BACKTEST_SCRIPT = r'D:\QClaw_Trading\backtest_v4_fixed.py'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'

# 测试配置
configs = [
    {
        'name': '原版v4.3（等权重，无过滤）',
        'args': '--lb 3 --max-dev 10 --top-n 2 --hs300-threshold -100'
    },
    {
        'name': '优化版v4.4（动态仓位，无成交量过滤）',
        'args': '--lb 3 --max-dev 10 --top-n 2 --hs300-threshold -100 --dynamic-weight'
    },
    {
        'name': '优化版v4.4（动态仓位+成交量过滤）',
        'args': '--lb 3 --max-dev 10 --top-n 2 --hs300-threshold -100 --dynamic-weight --volume-filter'
    }
]

def run_backtest(config):
    """运行单次回测"""
    cmd = f'python "{BACKTEST_SCRIPT}" {config["args"]}'
    print(f"\n{'='*60}")
    print(f"运行: {config['name']}")
    print(f"命令: {cmd}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    # 解析输出（简单解析，实际应该解析JSON）
    output = result.stdout + result.stderr
    
    # 提取关键指标（简单实现）
    lines = output.split('\n')
    stats = {}
    for line in lines:
        if 'Annual:' in line:
            stats['annual'] = line.split(':')[1].strip()
        elif 'Sharpe:' in line:
            stats['sharpe'] = line.split(':')[1].strip()
        elif 'Max DD:' in line:
            stats['max_dd'] = line.split(':')[1].strip()
        elif 'Total Ret:' in line:
            stats['total_ret'] = line.split(':')[1].strip()
    
    return stats

def main():
    print("开始对比回测...")
    print(f"回测脚本: {BACKTEST_SCRIPT}")
    print(f"输出目录: {OUTPUT_DIR}\n")
    
    results = []
    for config in configs:
        stats = run_backtest(config)
        results.append({
            'name': config['name'],
            'stats': stats
        })
    
    # 输出对比表格
    print(f"\n{'='*80}")
    print("对比结果")
    print(f"{'='*80}\n")
    print(f"{'版本':<50} {'年化':>8} {'夏普':>8} {'最大回撤':>10}")
    print(f"{'-'*80}")
    
    for r in results:
        name = r['name'][:48] + '..' if len(r['name']) > 50 else r['name']
        annual = r['stats'].get('annual', 'N/A')
        sharpe = r['stats'].get('sharpe', 'N/A')
        max_dd = r['stats'].get('max_dd', 'N/A')
        print(f"{name:<50} {annual:>8} {sharpe:>8} {max_dd:>10}")
    
    print(f"\n{'='*80}")
    print("回测完成！")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()
