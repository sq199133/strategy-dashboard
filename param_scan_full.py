#!/usr/bin/env python3
"""完整参数扫描 - 直接调用函数，高效执行"""
import sys
import json
import time
from datetime import datetime
from itertools import product

sys.path.insert(0, 'D:/QClaw_Trading')

# 导入核心函数
from backtest_v4_fixed import (
    load_pool, load_history, load_hs300_momentum,
    compute_momentum, compute_ma, compute_deviation
)

def run_backtest(params, start_week, end_week, hs300_threshold=-100.0):
    """高效回测函数 - 直接调用核心逻辑"""
    ma_s, ma_l, lb, max_dev, top_n = params
    
    # 加载数据（只加载一次）
    if not hasattr(run_backtest, 'cache'):
        run_backtest.cache = {}
        run_backtest.cache['pool'] = load_etf_pool()
        run_backtest.cache['hs300_mom'] = load_hs300_momentum()
        
        # 加载所有ETF历史数据
        all_series = {}
        for code in run_backtest.cache['pool']:
            hist = load_history(code)
            if hist:
                all_series[code] = hist
        run_backtest.cache['all_series'] = all_series
        
        # 生成完整周序列
        all_weeks = sorted(set(w for code in all_series.values() for w, _ in code))
        run_backtest.cache['all_weeks'] = all_weeks
    
    pool = run_backtest.cache['pool']
    all_series = run_backtest.cache['all_series']
    all_weeks = run_backtest.cache['all_weeks']
    hs300_mom = run_backtest.cache['hs300_mom'] if hs300_threshold > -100 else None
    
    # 筛选时间段
    weeks = [w for w in all_weeks if start_week <= w <= end_week]
    if len(weeks) < ma_l + lb + 2:
        return None
    
    # 初始化
    equity = 1.0
    positions = []  # [(code, cost, entry_week), ...]
    equity_curve = []
    peak = 1.0
    max_dd = 0.0
    trades_buy = trades_sell = 0
    
    # 逐周回测
    for i, week in enumerate(weeks):
        # 计算本周权益
        week_return = 0.0
        if positions:
            for j, (code, cost, entry_w) in enumerate(positions):
                if code in all_series:
                    closes = [c for w, c in all_series[code] if w <= week]
                    if len(closes) >= 1:
                        ret = (closes[-1] / cost - 1) if i > 0 else 0
                        week_return += ret / len(positions)
            equity *= (1 + week_return)
        
        # 更新峰值和回撤
        if equity > peak:
            peak = equity
        dd = (equity / peak - 1) * 100
        if dd < max_dd:
            max_dd = dd
        
        equity_curve.append(equity)
        
        # 检查止损
        new_positions = []
        for code, cost, entry_w in positions:
            should_sell = False
            if code in all_series:
                closes = [c for w, c in all_series[code] if w <= week]
                if len(closes) >= 1:
                    cur_price = closes[-1]
                    # 成本止损
                    if cur_price / cost - 1 < -0.08:
                        should_sell = True
                    # 高点回撤止损
                    high = max(c for w, c in all_series[code] if w <= week)
                    if cur_price / high - 1 < -0.10:
                        should_sell = True
            if not should_sell:
                new_positions.append((code, cost, entry_w))
            else:
                trades_sell += 1
        positions = new_positions
        
        # 筛选合格ETF
        qualified = []
        for code in pool:
            if code not in all_series:
                continue
            closes = [c for w, c in all_series[code] if w <= week]
            if len(closes) < ma_l + lb + 2:
                continue
            
            # 计算动量
            mom = compute_momentum(closes, lb)
            if mom is None or mom <= 0:
                continue
            
            # 计算MA
            ma_short = compute_ma(closes, ma_s)
            ma_long = compute_ma(closes, ma_l)
            if ma_short is None or ma_long is None or ma_short <= ma_long:
                continue
            
            # 计算偏离度
            dev = compute_deviation(closes[-1], ma_short)
            if dev is None or dev > max_dev:
                continue
            
            # G3过滤
            if len(closes) >= 4:
                w3_mom = (closes[-1] / closes[-4] - 1) * 100
                if w3_mom < 0:
                    continue
            if len(closes) >= 2:
                w1_ret = (closes[-1] / closes[-2] - 1) * 100
                if w1_ret < -1:
                    continue
            
            # HS300过滤
            if hs300_mom and week in hs300_mom:
                if hs300_mom[week] <= hs300_threshold / 100:
                    continue
            
            qualified.append((code, mom, dev))
        
        # 排序并选择
        qualified.sort(key=lambda x: x[1], reverse=True)
        target_codes = [x[0] for x in qualified[:top_n]]
        
        # 调仓
        current_codes = [x[0] for x in positions]
        for code in current_codes:
            if code not in target_codes:
                positions = [x for x in positions if x[0] != code]
                trades_sell += 1
        
        for code in target_codes:
            if code not in current_codes:
                if code in all_series:
                    closes = [c for w, c in all_series[code] if w <= week]
                    if len(closes) >= 1:
                        positions.append((code, closes[-1], week))
                        trades_buy += 1
        
        # 空仓处理
        if not target_codes and positions:
            positions = []
            trades_sell += len(current_codes)
    
    # 计算指标
    if len(equity_curve) < 2:
        return None
    
    total_ret = (equity_curve[-1] / equity_curve[0] - 1) * 100
    years = len(weeks) / 52.0
    annual = (1 + total_ret/100) ** (1/years) - 1 if years > 0 else 0
    annual *= 100
    
    # 夏普比率（简化）
    returns = []
    for i in range(1, len(equity_curve)):
        ret = (equity_curve[i] / equity_curve[i-1] - 1)
        returns.append(ret)
    
    if returns:
        avg_ret = sum(returns) / len(returns)
        std_ret = (sum((r - avg_ret)**2 for r in returns) / len(returns)) ** 0.5
        sharpe = (avg_ret / std_ret) * (52**0.5) if std_ret > 0 else 0
    else:
        sharpe = 0
    
    return {
        'annual': annual,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'total_ret': total_ret,
        'trades_buy': trades_buy,
        'trades_sell': trades_sell
    }

# 参数网格
ma_combos = [(5, 21)]  # 固定MA
lb_range = range(1, 22)  # LB=1-21
dev_range = [5, 10, 15, 20]  # 偏离度
top_n = 3

print("=" * 80)
print("完整参数扫描（分半验证）")
print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
print(f"参数空间: MA5/21, LB=1-21, Dev={dev_range}, Top{top_n}")
print(f"总组合数: {len(ma_combos) * len(lb_range) * len(dev_range)}")
print(f"分半验证: 2010-2018 vs 2019-2026")
print("=" * 80)

results = []
total = len(ma_combos) * len(lb_range) * len(dev_range)
done = 0
start_time = time.time()

for ma_s, ma_l in ma_combos:
    for lb in lb_range:
        for dev in dev_range:
            params = (ma_s, ma_l, lb, dev, top_n)
            
            # 样本内（2010-2018）
            r1 = run_backtest(params, '2010-W01', '2018-W52')
            
            # 样本外（2019-2026）
            r2 = run_backtest(params, '2019-W01', '2026-W18')
            
            if r1 and r2:
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
            
            # 每10个组合输出一次进度
            if done % 10 == 0:
                elapsed = time.time() - start_time
                eta = (elapsed / done) * (total - done) / 60
                print(f"[{done}/{total}] 进度={done/total*100:.1f}% "
                      f"用时={elapsed/60:.1f}分钟 ETA={eta:.1f}分钟")
            
            # 每小时保存一次中间结果
            if done % 20 == 0:
                interim_file = f"D:/QClaw_Trading/backtest_results/param_scan_interim_{done}.json"
                with open(interim_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

# 按稳健性得分排序
results.sort(key=lambda x: x['robust_score'] or 0, reverse=True)

# 输出前20
print("\n" + "=" * 80)
print("前20名稳健参数组合（分半验证）:")
print("=" * 80)
for i, r in enumerate(results[:20]):
    p = r['params']
    ins = r['in_sample']
    out = r['out_sample']
    print(f"{i+1:2}. MA{p[0]}/{p[1]} LB{p[2]} D{p[3]} H{p[4]} "
          f"得分={r['robust_score']:.2f}")
    if ins:
        print(f"    样本内: 年化{ins['annual']:.1f}% 夏普{ins['sharpe']:.2f} "
              f"回撤{ins['max_dd']:.1f}%")
    if out:
        print(f"    样本外: 年化{out['annual']:.1f}% 夏普{out['sharpe']:.2f} "
              f"回撤{out['max_dd']:.1f}%")
    print()

# 保存最终结果
output_file = (f"D:/QClaw_Trading/backtest_results/"
               f"param_scan_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

elapsed_total = (time.time() - start_time) / 60
print("=" * 80)
print(f"扫描完成！")
print(f"总用时: {elapsed_total:.1f}分钟")
print(f"结果已保存: {output_file}")
print("=" * 80)
