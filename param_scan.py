#!/usr/bin/env python3
"""参数扫描：LB=1-21, 偏离度=5%-20%, 分半验证"""
import sys
import json
from datetime import datetime

# 导入回测函数
sys.path.insert(0, 'D:/QClaw_Trading')
from backtest_v4_fixed import load_etf_pool, load_history, load_hs300_momentum

def backtest(params, start_week, end_week, hs300_threshold=-100.0):
    """运行单次回测，返回结果字典"""
    ma_s, ma_l, lb, max_dev, top_n = params
    
    # 加载数据
    pool = load_etf_pool()
    all_series = {}
    for code in pool:
        hist = load_history(code)
        if hist:
            all_series[code] = hist
    
    # 加载HS300（但阈值-100时跳过）
    hs300_mom = load_hs300_momentum() if hs300_threshold > -100 else None
    
    # 生成周序列
    all_weeks = sorted(set(w for code in all_series.values() for w, _ in code))
    all_weeks = [w for w in all_weeks if start_week <= w <= end_week]
    
    # 回测逻辑（简化版，直接调用backtest_v4_fixed的主逻辑）
    # 为节省时间，这里用subprocess调用backtest_v4_fixed.py
    import subprocess
    cmd = [
        'python', 'backtest_v4_fixed.py',
        '--ma-s', str(ma_s),
        '--ma-l', str(ma_l),
        '--lb', str(lb),
        '--max-dev', str(max_dev),
        '--top-n', str(top_n),
        '--hs300-threshold', str(hs300_threshold),
        '--start', start_week,
        '--end', end_week
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd='D:/QClaw_Trading')
    
    # 解析输出（简化：查找Annual和Sharpe行）
    output = result.stdout
    annual = sharpe = max_dd = None
    for line in output.split('\n'):
        if 'Annual:' in line:
            annual = float(line.split(':')[1].strip().replace('%', ''))
        elif 'Sharpe:' in line:
            sharpe = float(line.split(':')[1].strip())
        elif 'Max DD:' in line:
            max_dd = float(line.split(':')[1].strip().replace('%', ''))
    
    return {
        'annual': annual,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'params': params
    }

# 参数网格
ma_combos = [(5, 21)]  # 固定MA组合
lb_range = range(1, 22)  # LB=1-21
dev_range = range(5, 21, 5)  # 偏离度5%,10%,15%,20%
top_n = 3

print("开始参数扫描...")
print("参数组合: MA5/21, LB=1-21, Dev=5%-20%, Top3")
print("分半验证: 2010-2018 vs 2019-2026")
print("=" * 60)

results = []
total = len(ma_combos) * len(lb_range) * len(dev_range)
done = 0

for ma_s, ma_l in ma_combos:
    for lb in lb_range:
        for dev in dev_range:
            params = (ma_s, ma_l, lb, dev, top_n)
            
            # 样本内（2010-2018）
            r1 = backtest(params, '2010-W01', '2018-W52')
            
            # 样本外（2019-2026）
            r2 = backtest(params, '2019-W01', '2026-W18')
            
            # 计算稳健性得分（样本内和样本外夏普的平均）
            if r1['sharpe'] and r2['sharpe']:
                robust_score = (r1['sharpe'] + r2['sharpe']) / 2
            else:
                robust_score = None
            
            results.append({
                'params': params,
                'in_sample': r1,
                'out_sample': r2,
                'robust_score': robust_score
            })
            
            done += 1
            if done % 10 == 0:
                print(f"进度: {done}/{total} ({done/total*100:.1f}%)")

# 按稳健性得分排序
results.sort(key=lambda x: x['robust_score'] or 0, reverse=True)

# 输出前10
print("\n" + "=" * 60)
print("前10名稳健参数组合（分半验证）:")
print("=" * 60)
for i, r in enumerate(results[:10]):
    p = r['params']
    print(f"{i+1:2}. MA{p[0]}/{p[1]} LB{p[2]} D{p[3]} H{p[4]}")
    print(f"   样本内: 年化{p['in_sample']['annual']:.1f}% 夏普{p['in_sample']['sharpe']:.2f} 回撤{p['in_sample']['max_dd']:.1f}%")
    print(f"   样本外: 年化{p['out_sample']['annual']:.1f}% 夏普{p['out_sample']['sharpe']:.2f} 回撤{p['out_sample']['max_dd']:.1f}%")
    print(f"   稳健得分: {r['robust_score']:.2f}")
    print()

# 保存结果
output_file = f"D:/QClaw_Trading/backtest_results/param_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"结果已保存: {output_file}")