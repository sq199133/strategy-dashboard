"""
渐进式ETF加入分析 - 修正日期对齐问题
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy, DEFAULT_POOL)

N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

ALL_POOL = {
    "510050": "SH50",
    "159902": "ZZSM100",
    "159915": "CYB",
    "510300": "HS300",
    "518880": "GOLD",
    "159949": "CYB50",
    "512100": "ZZ1000",
}

# 预加载RSRS信号（用沪深300，所有版本共享）
df510 = load_etf("510300")
sig, zs, bt = compute_rsrs(df510, N, M, BUY, SELL)
sig_series = pd.Series(sig, index=pd.to_datetime(df510["date"].values))

# 预计算波动率缩放
vol_scaling_raw = compute_vol_scaling(df510, pd.to_datetime(df510["date"].values), VW, TV)

# 找出最早的有效信号日期（RSRS需要900天）
first_sig_date = sig_series.index[M]
print(f"  RSRS首有效信号: {first_sig_date.date()}")
print(f"  RSRS信号总数: {len(sig_series)}")

# 获取每个ETF的可用起始日期
data_cache = {}
pool_start = {}
for code in ALL_POOL:
    raw = load_etf(code)
    data_cache[code] = raw
    # 需要至少200条数据才能用
    if len(raw) > 200:
        pool_start[code] = raw["date"].iloc[200]
    else:
        pool_start[code] = raw["date"].iloc[0]
    print(f"  {code:>6} {ALL_POOL[code]:<8}  可用始于: {pool_start[code].date()}")

sorted_codes = sorted(pool_start.keys(), key=lambda c: pool_start[c])
print(f"\n  加入顺序:")
for i, c in enumerate(sorted_codes):
    print(f"    {i+1}. {c} {ALL_POOL[c]:<8}  {pool_start[c].date()}")

def run_backtest_pool(code_list, label):
    pool = {c: ALL_POOL[c] for c in code_list}
    try:
        data, panel = build_panel(pool, min_rows=200)
    except Exception as e:
        return None
    
    # 对齐到RSRS可用日期
    panel = panel[panel.index >= first_sig_date]
    if len(panel) < 20:
        return None
    
    # 子集信号
    valid_sig = sig_series[sig_series.index.isin(panel.index)]
    
    mom_data = compute_momentum(data, panel)
    
    # 波动率缩放对齐
    vol_scaling = vol_scaling_raw[vol_scaling_raw.index.isin(panel.index)]
    
    positions = run_strategy(data, panel, sig_series.values, sig_series.index.values, 
                             mom_data, RB, TOP, vol_scaling)

    daily_ret = panel.pct_change().fillna(0)
    ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)
    ret = ret[ret.index >= first_sig_date]
    
    if len(ret) < 20:
        return None
    
    eq = (1 + ret).cumprod()
    cagr_total = eq.iloc[-1] ** (252 / len(ret)) - 1
    sharpe_total = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd_total = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100

    years = sorted(set(d.year for d in ret.index))
    annual = {}
    for yr in years:
        mask = ret.index.year == yr
        nd = mask.sum()
        if nd < 10: continue
        yr_ret = ret[mask]
        yr_eq = (1 + yr_ret).cumprod()
        cagr = yr_eq.iloc[-1] ** (252 / nd) - 1
        sharpe = np.sqrt(252) * yr_ret.mean() / yr_ret.std() if yr_ret.std() > 1e-10 else 0
        mdd = ((yr_eq - yr_eq.cummax()) / yr_eq.cummax()).min()
        annual[yr] = {"cagr": round(cagr*100,1), "sharpe": round(sharpe,2), "mdd": round(mdd*100,1)}

    return {
        "pool": {c: ALL_POOL[c] for c in code_list},
        "codes": code_list,
        "n": len(code_list),
        "total_cagr": round(cagr_total*100,1),
        "total_sharpe": round(sharpe_total,2),
        "total_mdd": round(mdd_total*100,1),
        "win_rate": round(wr,1),
        "days": len(ret),
        "annual": annual,
        "start": ret.index[0],
        "end": ret.index[-1],
    }

print(f"\n  === 渐进加入回测 ===\n")
results = []
for i in range(len(sorted_codes)):
    codes = sorted_codes[:i+1]
    label = "+".join([ALL_POOL[c] for c in codes])
    r = run_backtest_pool(codes, label)
    if r:
        results.append(r)
        new_code = codes[-1]
        print(f"[{i+1}] ADD {new_code} {ALL_POOL[new_code]}  "
              f"CAGR:{r['total_cagr']:>5.1f}%  Sharpe:{r['total_sharpe']:.2f}  "
              f"MDD:{r['total_mdd']:>5.1f}%  Win:{r['win_rate']:.1f}%  "
              f"[{r['start'].date()}~{r['end'].date()}]")
        if len(results) > 1:
            prev = results[-2]
            dc = r['total_cagr'] - prev['total_cagr']
            print(f"      >> 增量 CAGR: {dc:+.1f}%")

# 年度对比表
all_years = sorted(set(y for r in results for y in r['annual'].keys()))
print(f"\n\n{'='*110}")
print(f"  {'年份':<5}", end="")
for r in results:
    last = list(r['pool'].keys())[-1]
    print(f"  {r['n']}ETF({ALL_POOL[last]:<6})", end="")
print()

print(f"  {'-'*110}")
for yr in all_years:
    print(f"  {yr:<5}", end="")
    for r in results:
        if yr in r['annual']:
            print(f"  {r['annual'][yr]['cagr']:>8.1f}%    ", end="")
        else:
            print(f"  {' -':>8}     ", end="")
    print()

# 增量明细
print(f"\n\n  增量收益明细（每加入一个ETF后的性能变化）:")
print(f"  {'新ETF':<6} {'名称':<10} {'加入后CAGR':>10} {'CAGR增量':>9} {'夏普':>5} {'MDD%':>6}")
print(f"  {'-'*55}")
prev_r = None
for r in results:
    new_code = r['codes'][-1]
    new_name = ALL_POOL[new_code]
    if prev_r is None:
        print(f"  {new_code:<6} {new_name:<10} {r['total_cagr']:>10.1f}%  {'(初始)':>9} {r['total_sharpe']:>5.2f} {r['total_mdd']:>6.1f}%")
    else:
        dc = r['total_cagr'] - prev_r['total_cagr']
        ds = r['total_sharpe'] - prev_r['total_sharpe']
        dm = r['total_mdd'] - prev_r['total_mdd']
        arrow = "+ " if dc >= 0 else ""
        print(f"  {new_code:<6} {new_name:<10} {r['total_cagr']:>10.1f}%  {arrow}{dc:>+7.1f}% {r['total_sharpe']:>5.2f} {r['total_mdd']:>6.1f}%")
    prev_r = r
