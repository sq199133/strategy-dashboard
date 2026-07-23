#!/usr/bin/env python3
"""并行参数扫描 - 同时跑4个回测"""
import subprocess
import json
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

def run_single_backtest(params, period):
    """跑单次回测，返回结果字典"""
    ma_s, ma_l, lb, max_dev, top_n = params
    start, end = period
    
    cmd = [
        'python', 'backtest_v4_fixed.py',
        '--ma-s', str(ma_s),
        '--ma-l', str(ma_l),
        '--lb', str(lb),
        '--max-dev', str(max_dev),
        '--top-n', str(top_n),
        '--hs300-threshold', '-100',
        '--start', start,
        '--end', end
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd='D:/QClaw_Trading',
        timeout=300  # 5分钟超时
    )
    
    # 解析输出
    output = result.stdout
    annual = sharpe = max_dd = None
    for line in output.split('\n'):
        if 'Annual:' in line:
            try:
                annual = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        elif 'Sharpe:' in line:
            try:
                sharpe = float(line.split(':')[1].strip())
            except:
                pass
        elif 'Max DD:' in line:
            try:
                max_dd = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
    
    return {
        'params': params,
        'period': period,
        'annual': annual,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'success': annual is not None
    }

# 参数网格（关键参数）
ma_combos = [(5, 21)]
lb_range = range(1, 9)  # LB=1-8
dev_range = [5, 10, 15]  # 偏离度5%,10%,15%
top_n = 3

periods = [
    ('2010-W01', '2018-W52'),  # 样本内
    ('2019-W01', '2026-W18'),  # 样本外
]

print("=" * 80)
print("并行参数扫描（关键参数）")
print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"参数: LB=1-8, Dev=5%-15%")
print(f"并行数: 4")
print("=" * 80)

# 生成所有任务
tasks = []
for ma_s, ma_l in ma_combos:
    for lb in lb_range:
        for dev in dev_range:
            params = (ma_s, ma_l, lb, dev, top_n)
            for period in periods:
                tasks.append((params, period))

print(f"总任务数: {len(tasks)}")
print("=" * 80)

# 并行执行
results = []
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(run_single_backtest, params, period): (params, period) 
               for params, period in tasks}
    
    done = 0
    for future in as_completed(futures):
        done += 1
        try:
            result = future.result()
            results.append(result)
            
            if done % 10 == 0:
                print(f"进度: {done}/{len(tasks)} ({done/len(tasks)*100:.1f}%)")
        except Exception as e:
            print(f"任务失败: {e}")

print("=" * 80)
print("所有任务完成，开始汇总...")

# 汇总结果（分半验证）
final_results = []
for ma_s, ma_l in ma_combos:
    for lb in lb_range:
        for dev in dev_range:
            params = (ma_s, ma_l, lb, dev, top_n)
            
            # 找样本内和样本外结果
            in_sample = next((r for r in results 
                             if r['params'] == params 
                             and r['period'] == periods[0]), None)
            out_sample = next((r for r in results 
                              if r['params'] == params 
                              and r['period'] == periods[1]), None)
            
            if in_sample and out_sample and in_sample['success'] and out_sample['success']:
                robust_score = (in_sample['sharpe'] + out_sample['sharpe']) / 2
                final_results.append({
                    'params': params,
                    'in_sample': in_sample,
                    'out_sample': out_sample,
                    'robust_score': robust_score
                })

# 排序
final_results.sort(key=lambda x: x['robust_score'], reverse=True)

# 输出前10
print("\n前10名稳健参数组合:")
print("=" * 80)
for i, r in enumerate(final_results[:10]):
    p = r['params']
    print(f"{i+1:2}. MA{p[0]}/{p[1]} LB{p[2]} D{p[3]} H{p[4]} "
          f"得分={r['robust_score']:.2f}")
    print(f"    样本内: 年化{r['in_sample']['annual']:.1f}% "
          f"夏普{r['in_sample']['sharpe']:.2f}")
    print(f"    样本外: 年化{r['out_sample']['annual']:.1f}% "
          f"夏普{r['out_sample']['sharpe']:.2f}")
    print()

# 保存
output_file = (f"D:/QClaw_Trading/backtest_results/"
               f"param_scan_parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(final_results, f, indent=2, ensure_ascii=False)

print(f"结果已保存: {output_file}")
print("=" * 80)