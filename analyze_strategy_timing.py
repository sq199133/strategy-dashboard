"""
策略择时分析：是否需要在策略表现不好时暂停交易？
"""
import json, glob, os
import numpy as np
from collections import defaultdict

# 加载最新回测结果
result_dir = r'D:\QClaw_Trading\backtest_results'
files = sorted(glob.glob(os.path.join(result_dir, 'bt_*.json')), key=os.path.getmtime)
with open(files[-1]) as f:
    data = json.load(f)

eq = data['equity']  # [{w, eq, nh}]
eq_prices = [x['eq'] for x in eq]
weeks = [x['w'] for x in eq]

print(f"回测期: {weeks[0]} ~ {weeks[-1]} ({len(weeks)}周)")

# ===== 1. 策略本身的回撤分析 =====
peak = eq_prices[0]
max_dd = 0
max_dd_start = 0
current_dd = 0
in_drawdown = False
dd_periods = []  # [(start_w, end_w, depth, recovery_to_peak, n_trades_in_dd)]
drawdown_start = None

for i, (w, p) in enumerate(zip(weeks, eq_prices)):
    if p > peak:
        if in_drawdown:
            # Recovery complete
            depth = (peak - eq_prices[drawdown_start]) / peak * 100
            dd_periods.append((weeks[drawdown_start], w, depth, i - drawdown_start))
            in_drawdown = False
        peak = p
    
    dd = (peak - p) / peak * 100
    if dd > 5:  # 5%+ drawdown
        if not in_drawdown:
            drawdown_start = i
            in_drawdown = True
        if dd > max_dd:
            max_dd = dd
            max_dd_start = i
    else:
        if in_drawdown and dd < 2:  # recovered to within 2%
            depth = (peak - eq_prices[drawdown_start]) / peak * 100
            dd_periods.append((weeks[drawdown_start], w, depth, i - drawdown_start))
            in_drawdown = False

print(f"\n=== 1. 历史最大回撤 ===")
print(f"最大回撤: {max_dd:.1f}%")
print(f"大于5%的回撤次数: {len(dd_periods)}")

# 列出前10大回撤
dd_sorted = sorted(dd_periods, key=lambda x: -x[2])
print(f"\n前10大回撤:")
print(f"{'开始':>10} {'结束':>10} {'深度':>8} {'持续周数':>8}")
for sw, ew, depth, dur in dd_sorted[:10]:
    print(f"{sw:>10} {ew:>10} {depth:>7.1f}% {dur:>8}周")

# ===== 2. 连续亏损周分析 =====
print(f"\n=== 2. 连续亏损周分析 ===")
weekly_ret = []
for i in range(1, len(eq_prices)):
    r = (eq_prices[i] / eq_prices[i-1] - 1) * 100
    weekly_ret.append(r)

# 找连续亏损
max_losing_streak = 0
current_streak = 0
streaks = []
for i, r in enumerate(weekly_ret):
    if r < 0:
        current_streak += 1
    else:
        if current_streak >= 3:  # 3周以上连续亏损
            streaks.append((current_streak, weeks[i - current_streak + 1], weeks[i]))
        max_losing_streak = max(max_losing_streak, current_streak)
        current_streak = 0
if current_streak >= 3:
    streaks.append((current_streak, weeks[-current_streak], weeks[-1]))

print(f"最长连续亏损周: {max_losing_streak}")
print(f"连续亏损≥3周共 {len(streaks)} 次:")
for n, sw, ew in sorted(streaks, reverse=True)[:10]:
    print(f"  连续{n}周亏损: {sw} ~ {ew}")

# ===== 3. 策略在不同市场下的表现 =====
print(f"\n=== 3. 年份收益分析 ===")
# 从stats里没有逐年数据，直接从backtest输出看

# ===== 4. 模拟择时策略：当策略从高点回撤超过阈值时暂停 =====
print(f"\n=== 4. 模拟择时方案 ===")
# 方案A: 策略自身回撤 > X%时暂停，恢复至新高时重启
# 方案B: 当池中合格ETF数量少于阈值时暂停
# 方案C: 连续N周亏损时暂停，连涨N周时重启

thresholds = [5, 8, 10, 12, 15]

for dd_thresh in thresholds:
    peak = eq_prices[0]
    cash = 1.0
    strategy_active = True
    cash_mode = False
    cash_start_week = None
    cash_duration = 0
    cash_count = 0
    
    for i, (w, p) in enumerate(zip(weeks, eq_prices)):
        if p > peak:
            peak = p
        
        dd_from_peak = (peak - p) / peak * 100
        
        if strategy_active and dd_from_peak > dd_thresh:
            # Enter cash mode at peak value
            cash = peak  # Lock in at peak
            strategy_active = False
            cash_mode = True
            cash_start_week = w
            cash_count += 1
        elif cash_mode and p > peak:  # Recovered to new high
            strategy_active = True
            cash_mode = False
            cash_duration += 1  # not accurate per-period count, just count events
    
    # Final value: if in cash mode, use locked cash + any growth from risk-free
    # Simplified: just use the peak value locked
    # Actually let me do this more carefully
    
print("(精确计算见下)")

# ===== 更精确的回撤暂停策略 =====
print(f"\n{'方案':<15} {'年化':>8} {'夏普':>8} {'最大回撤':>10} {'累计':>10}")
print("-" * 55)

# Baseline
total_ret = eq_prices[-1] / eq_prices[0] - 1
years = len(weeks) / 52
ann = (eq_prices[-1] / eq_prices[0]) ** (1/years) - 1
print(f"{'基线(无择时)':<15} {ann*100:>7.1f}% {0.93:>7.2f} {max_dd:>9.1f}% {total_ret*100:>9.1f}%")

# 方案1: 回撤阈值暂停（策略净值从高点回撤X%时清仓，新高时恢复）
# 方案2: 连续亏损暂停（连续N周亏损时清仓）
# 方案3: 合格数量暂停（当期合格ETF少于N只时清仓）

# 方案1 - 回撤阈值
for dd_thresh in [8, 10, 12, 15]:
    peak_val = eq_prices[0]
    eq_with_dd_stop = []
    in_cash = False
    cash_value = eq_prices[0]
    
    for p in eq_prices:
        if p > peak_val:
            peak_val = p
            if in_cash:
                # Return to market at new high
                in_cash = False
        
        dd = (peak_val - p) / peak_val * 100
        
        if not in_cash:
            if dd > dd_thresh:
                in_cash = True
                cash_value = peak_val  # Lock cash at peak
            eq_with_dd_stop.append(p)
        else:
            eq_with_dd_stop.append(cash_value)  # Stay at locked value
    
    final = eq_with_dd_stop[-1]
    tr = final / eq_with_dd_stop[0] - 1
    ann_ret = (final / eq_with_dd_stop[0]) ** (1/years) - 1
    
    # Calculate max DD
    pk = eq_with_dd_stop[0]
    mdd = 0
    for v in eq_with_dd_stop:
        if v > pk:
            pk = v
        dd_cur = (pk - v) / pk * 100
        if dd_cur > mdd:
            mdd = dd_cur
    
    print(f"{f'DD≥{dd_thresh}%暂停':<15} {ann_ret*100:>7.1f}% {'':>7} {mdd:>9.1f}% {tr*100:>9.1f}%")

# 方案2 - 连续亏损N周暂停
for n_loss in [3, 4, 5, 6]:
    eq_consec = [eq_prices[0]]
    loss_count = 0
    recovered = True
    
    for i in range(1, len(eq_prices)):
        r = eq_prices[i] / eq_prices[i-1] - 1
        if r < 0:
            loss_count += 1
        else:
            loss_count = 0
            if not recovered:
                recovered = True
        
        if loss_count >= n_loss:
            # go to cash at this point
            # Stay at previous value
            eq_consec.append(eq_consec[-1])
            recovered = False
            loss_count = n_loss  # prevent re-triggering
        else:
            eq_consec.append(eq_prices[i])
    
    final = eq_consec[-1]
    tr = final / eq_consec[0] - 1
    ann_ret = (final / eq_consec[0]) ** (1/years) - 1
    
    pk = eq_consec[0]
    mdd = 0
    for v in eq_consec:
        if v > pk:
            pk = v
        dd_cur = (pk - v) / pk * 100
        if dd_cur > mdd:
            mdd = dd_cur
    
    print(f"{f'连亏{n_loss}周暂停':<15} {ann_ret*100:>7.1f}% {'':>7} {mdd:>9.1f}% {tr*100:>9.1f}%")

print(f"\n{'='*60}")
print(f"注：夏普未计算（简化模拟），只看年化和回撤影响")
