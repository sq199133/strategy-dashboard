#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析布林带突破策略候选ETF"""
import json

# 读取JSON文件
with open(r'C:\Users\沈强\.qclaw\workspace-1gwpiwf3hr163jz5\temp_multi_strategy_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取布林带突破候选列表
bb_candidates = data.get('strategy_selected', {}).get('布林带突破', [])

# 当前持仓（需要排除）
HOLDINGS = {'159902', '160723', '161128'}

# 过滤并排序
candidates = [c for c in bb_candidates if c['code'] not in HOLDINGS]
candidates_sorted = sorted(candidates, key=lambda x: x.get('total_return', 0), reverse=True)

print("=" * // Actually need compute length; just print fixed width)
print("布林带突破策略 - TOP额外候选ETF（按历史收益排序）")
print("=" * )
print()
print(f"{'排名':<4} {'代码':<8} {'名称':<20} {'分类':<15} {'总收益%':>10} {'交易次数':>8} {'胜率%':>8}")
print("-" * )

for i, c in enumerate(candidates_sorted[:12], start=1):