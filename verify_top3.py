#!/usr/bin/env python3
"""全样本验证前3名参数"""
import subprocess
import json
import os

def run_backtest(params, output_file):
    """跑单次回测"""
    ma_s, ma_l, lb, max_dev, top_n = params
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    cmd = [
        'python', 'backtest_v4_fixed.py',
        '--ma-s', str(ma_s),
        '--ma-l', str(ma_l),
        '--lb', str(lb),
        '--max-dev', str(max_dev),
        '--top-n', str(top_n),
        '--hs300-threshold', '-100',
        '--start', '2010-W01',
        '--end', '2026-W18',
        '--output', output_file
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd='D:/QClaw_Trading',
        timeout=300
    )
    
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            stats = data.get('stats', {})
            return {
                'annual': stats.get('ann_ret', 0),
                'sharpe': stats.get('sharpe', 0),
                'max_dd': stats.get('max_dd', 0) * 100,
                'total_ret': stats.get('total_ret', 0),
                'win_rate': stats.get('win_rate', 0)
            }
    
    return None

# 前3名参数
top3 = [
    {'rank': 1, 'params': (5, 21, 3, 10, 2), 'label': 'MA5/21 LB3 D10 H2'},
    {'rank': 2, 'params': (5, 21, 3, 10, 3), 'label': 'MA5/21 LB3 D10 H3'},
    {'rank': 3, 'params': (5, 21, 4, 10, 3), 'label': 'MA5/21 LB4 D10 H3'},
]

print("=" * 70)
print("全样本验证（2010-W01 ~ 2026-W18）")
print("=" * 70)

results = []
for item in top3:
    params = item['params']
    output_file = (f"D:/QClaw_Trading/backtest_results/"
                   f"verify_{params[0]}_{params[1]}_{params[2]}_"
                   f"{params[3]}_{params[4]}.json")
    
    print(f"\n正在验证: {item['label']}")
    
    r = run_backtest(params, output_file)
    if r:
        results.append({
            'rank': item['rank'],
            'label': item['label'],
            'params': params,
            'result': r
        })
        print(f"  完成: 年化{r['annual']:.1f}% 夏普{r['sharpe']:.2f} "
              f"回撤{r['max_dd']:.1f}% 累计{r['total_ret']:+.1f}%")
    else:
        print("  失败")

print("\n" + "=" * 70)
print("全样本排名:")
print("=" * 70)
print(f"{'排名':<4} {'参数':<25} {'年化':>7} {'夏普':>6} {'回撤':>7} {'累计':>8}")
print("-" * 70)

for i, item in enumerate(sorted(results, key=lambda x: x['result']['sharpe'], reverse=True)):
    r = item['result']
    print(f"{i+1:2}. {item['label']:<25} {r['annual']:>+6.1f}% {r['sharpe']:>5.2f} "
          f"{r['max_dd']:>6.1f}% {r['total_ret']:>+7.1f}%")

print("\n建议: 选择全样本夏普最高的参数组合")
