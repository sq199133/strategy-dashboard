"""
仔细验证策略择时模拟是否正确
"""
import json, glob, os
import numpy as np

result_dir = r'D:\QClaw_Trading\backtest_results'
files = sorted(glob.glob(os.path.join(result_dir, 'bt_*.json')), key=os.path.getmtime)
with open(files[-1]) as f:
    data = json.load(f)

eq = data['equity']
eq_prices = [x['eq'] for x in eq]
weeks = [x['w'] for x in eq]

print(f"复权因子范围: min={min(eq_prices):.2f}, max={max(eq_prices):.2f}")
print(f"首周({weeks[0]}): {eq_prices[0]:.2f}, 末周({weeks[-1]}): {eq_prices[-1]:.2f}")
total_ret_raw = eq_prices[-1] / eq_prices[0] - 1
print(f"满期收益: {total_ret_raw*100:.2f}%")

# 验证基线
years = len(weeks) / 52
ann_baseline = (eq_prices[-1] / eq_prices[0]) ** (1/years) - 1
print(f"年化: {ann_baseline*100:.1f}% (应该≈18.6%)")

# ===== 验证DD暂停方案 =====
def simulate_dd_stop(threshold_pct):
    """回撤X%时锁定在现金，新高时恢复"""
    peak = eq_prices[0]
    in_cash = False
    cash_value = eq_prices[0]
    result = []
    
    for i, p in enumerate(eq_prices):
        # Update peak if we're not in cash
        if not in_cash and p > peak:
            peak = p
        
        dd = (peak - p) / peak * 100 if peak > 0 else 0
        
        if not in_cash:
            if dd > threshold_pct:
                in_cash = True
                cash_value = peak  # Lock at peak
                # This week: we take the actual p (damage already done)
                result.append(p)
            else:
                result.append(p)
        else:
            if p > peak:
                # Recovery - back in market
                in_cash = False
                peak = p
                result.append(p)
            else:
                result.append(cash_value)
    
    return result

for thresh in [8, 10, 12, 15]:
    eq_mod = simulate_dd_stop(thresh)
    
    # Debug: find where they diverge
    diffs = [(i, weeks[i], eq_prices[i], eq_mod[i]) 
             for i in range(len(eq_prices)) 
             if abs(eq_prices[i] - eq_mod[i]) > 0.001]
    
    tr_mod = eq_mod[-1] / eq_mod[0] - 1
    ann_mod = (eq_mod[-1] / eq_mod[0]) ** (1/years) - 1
    
    # Calculate max DD
    pk = eq_mod[0]
    mdd = 0
    for v in eq_mod:
        if v > pk:
            pk = v
        dd = (pk - v) / pk * 100
        if dd > mdd:
            mdd = dd
    
    print(f"\nDD≥{thresh}%方案:")
    print(f"  年化: {ann_mod*100:.1f}% (基线: {ann_baseline*100:.1f}%)")
    print(f"  累计: {tr_mod*100:.1f}% (基线: {total_ret_raw*100:.1f}%)")
    print(f"  最大回撤: {mdd:.1f}% (基线: 27.2%)")
    print(f"  触发事件: {len([d for d in diffs if d[2] != d[3]])} 次不同步")
    print(f"  首次触发: {diffs[0][1] if diffs else '无'} (原={diffs[0][2]:.2f}, 改={diffs[0][3]:.2f})" if diffs else "  未触发")
    
    # 检查是不是同一位置的差异
    if len(diffs) > 0:
        print(f"  最后差异: {diffs[-1][1]} (原={diffs[-1][2]:.2f}, 改={diffs[-1][3]:.2f})")
        
        # Count unique divergence periods
        divergence_periods = []
        in_div = False
        div_start = None
        for i, w, orig, mod in diffs:
            if not in_div:
                div_start = w
                in_div = True
            elif i < len(eq_prices) - 1:
                next_orig = eq_prices[i+1]
                next_mod = eq_mod[i+1]
                if abs(next_orig - next_mod) < 0.001:
                    in_div = False
                    divergence_periods.append((div_start, w))
        if in_div:
            divergence_periods.append((div_start, weeks[-1]))
        
        print(f"  分离散期数: {len(divergence_periods)}")
        for sw, ew in divergence_periods[:5]:
            print(f"    {sw} ~ {ew}")

# ===== 额外方案: 用回撤后NOT锁定在高峰，而是锁定在当前值 =====
print(f"\n{'='*60}")
print(f"修正方案: 不锁定高峰，锁定触发时的实际净值")
print(f"{'='*60}")

for thresh in [10]:
    peak = eq_prices[0]
    in_cash = False
    cash_value = eq_prices[0]
    result = []
    
    for i, p in enumerate(eq_prices):
        if not in_cash and p > peak:
            peak = p
        
        dd = (peak - p) / peak * 100 if peak > 0 else 0
        
        if not in_cash:
            if dd > thresh:
                in_cash = True
                cash_value = p  # Lock at current value, NOT peak!
                result.append(p)
            else:
                result.append(p)
        else:
            if p > peak:
                in_cash = False
                peak = p
                result.append(p)
            else:
                result.append(cash_value)
    
    tr = result[-1] / result[0] - 1
    ann = (result[-1] / result[0]) ** (1/years) - 1
    
    pk = result[0]
    mdd = 0
    for v in result:
        if v > pk:
            pk = v
        dd = (pk - v) / pk * 100
        if dd > mdd:
            mdd = dd
    
    print(f"DD≥{thresh}%(锁定净值): 年化={ann*100:.1f}%, 累计={tr*100:.1f}%, 最大回撤={mdd:.1f}%")
