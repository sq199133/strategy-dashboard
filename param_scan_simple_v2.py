#!/usr/bin/env python3
"""参数扫描 v2 - 修复JSON读取问题"""
import subprocess
import json
from datetime import datetime
import os

def run_backtest(params, start, end, output_file):
    """跑单次回测，读取指定的输出文件"""
    ma_s, ma_l, lb, max_dev, top_n = params
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    cmd = [
        'python', 'backtest_v4_fixed.py',
        '--ma-s', str(ma_s),
        '--ma-l', str(ma_l),
        '--lb', str(lb),
        '--max-dev', str(max_dev),
        '--top-n', str(top_n),
        '--hs300-threshold', '-100',
        '--start', start,
        '--end', end,
        '--output', output_file  # 指定输出文件
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd='D:/QClaw_Trading',
        timeout=300
    )
    
    # 读取指定的JSON文件
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            stats = data.get('stats', {})
            return {
                'annual': stats.get('ann_ret', 0),
                'sharpe': stats.get('sharpe', 0),
                'max_dd': stats.get('max_dd', 0) * 100  # 转成百分比
            }
    
    return None

# 参数（关键范围）
params_list = [
    (5, 21, 3, 10, 3),  # 当前默认
    (5, 21, 4, 10, 3),
    (5, 21, 5, 10, 3),
    (5, 21, 3, 5, 3),
    (5, 21, 3, 15, 3),
    (5, 21, 2, 10, 3),
    (5, 21, 2, 15, 3),
    (3, 13, 3, 10, 3),
    (10, 30, 3, 10, 3),
    (5, 21, 3, 10, 2),  # 持仓2只
]

periods = [
    ('2010-W01', '2018-W52'),
    ('2019-W01', '2026-W18'),
]

print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
print(f"总回测次数: {len(params_list) * len(periods)}")
print("=" * 60)

results = []
for params in params_list:
    for start, end in periods:
        # 生成唯一输出文件名
        p_str = f"{params[0]}_{params[1]}_{params[2]}_{params[3]}_{params[4]}"
        period_str = f"{start.replace('-', '')}_{end.replace('-', '')}"
        output_file = f"D:/QClaw_Trading/backtest_results/scan_{p_str}_{period_str}.json"
        
        print(f"正在跑: MA{params[0]}/{params[1]} LB{params[2]} D{params[3]} H{params[4]} {start}~{end}")
        
        r = run_backtest(params, start, end, output_file)
        if r:
            results.append({
                'params': params,
                'period': (start, end),
                'result': r
            })
            print(f"  完成: 年化{r['annual']:.1f}% 夏普{r['sharpe']:.2f}")
        else:
            print(f"  失败")
        
        # 保存中间结果
        interim = 'D:/QClaw_Trading/backtest_results/param_scan_interim.json'
        with open(interim, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

print("=" * 60)
print(f"结束时间: {datetime.now().strftime('%H:%M:%S')}")
print(f"完成回测: {len(results)}/{len(params_list) * len(periods)}")

# 计算稳健得分
final = {}
for params in params_list:
    in_sample = next((r['result'] for r in results 
                     if r['params'] == params 
                     and r['period'] == ('2010-W01', '2018-W52')), None)
    out_sample = next((r['result'] for r in results 
                      if r['params'] == params 
                      and r['period'] == ('2019-W01', '2026-W18')), None)
    
    if in_sample and out_sample:
        score = (in_sample['sharpe'] + out_sample['sharpe']) / 2
        final[params] = {
            'in': in_sample,
            'out': out_sample,
            'score': score
        }

# 排序输出
print("\n稳健参数排名:")
for i, (params, data) in enumerate(sorted(final.items(), key=lambda x: x[1]['score'], reverse=True)):
    p = params
    print(f"{i+1:2}. MA{p[0]}/{p[1]} LB{p[2]} D{p[3]} H{p[4]} "
          f"得分={data['score']:.2f}")
    print(f"    内: {data['in']['annual']:.1f}%/{data['in']['sharpe']:.2f} "
          f"外: {data['out']['annual']:.1f}%/{data['out']['sharpe']:.2f}")

# 保存最终结果
output_final = f"D:/QClaw_Trading/backtest_results/param_scan_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_final, 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)
print(f"\n结果已保存: {output_final}")