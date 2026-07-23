"""
最佳方案(M=900 RB=63 锁42d) - 分年持仓明细
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}
raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

M, rb, lock = 900, 63, 42
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
hold, lr, lku = [], None, None
rebal_dates, trade_log = [], []

for dt in panel.index:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    eff = raw_s
    if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
    if eff == 0: hold, lku = [], None; continue
    if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock)
    if lr is None or (dt - lr).days >= rb:
        scs = {}
        for c in POOL:
            if dt in mom[c].index:
                v = float(mom[c].loc[dt])
                if not np.isnan(v): scs[c] = v
        if not scs: hold = []; continue
        rk = sorted(scs.items(), key=lambda x: -x[1])
        sel = [c for c,v in rk if v>0]
        hold = sel[:1] if sel else []; lr = dt
        if hold: rebal_dates.append((dt, hold[0]))
    if hold:
        w = float(sc.loc[dt]) if dt in sc.index else 1.0
        if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w

dr = panel.pct_change().fillna(0)
ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
fs = pd.to_datetime(df_sig["date"].iloc[M])
ret = ret[ret.index >= fs]
eq = (1 + ret).cumprod()

print("="*100)
print("    分年持仓明细  |  M=900  RB=63  Lock=42")
print("="*100)
print(f"{'年份':>6} {'交易日':>6} {'收益%':>8} {'波动%':>7} {'胜率%':>7} {'持仓%':>7} {'调仓':>5}  {'持仓标的(占比)'}")
print("-"*100)

hold_pcts = {}
for yr in sorted(set(d.year for d in ret.index)):
    m = ret.index.year == yr
    nd = m.sum()
    if nd < 5: continue
    yr_ret = ret[m]
    yr_eq = (1 + yr_ret).cumprod()
    cagr = round((yr_eq.iloc[-1]**(252/nd)-1)*100, 1)
    vol = round(np.sqrt(252)*yr_ret.std()*100, 1)
    wr = round((yr_ret > 0).sum()/nd*100, 1)
    pr = round((pos.loc[yr_ret.index].sum(axis=1) > 0).mean()*100, 1)
    
    # 年内调仓次数
    yr_reb = sum(1 for dt, c in rebal_dates if dt.year == yr)
    
    # 该年持仓标的分布
    yr_pos = pos.loc[yr_ret.index]
    yr_counts = yr_pos.sum(axis=0)
    used = yr_counts[yr_counts > 0].sort_values(ascending=False)
    hold_str = ", ".join(f"{POOL.get(c,c)}({round(used[c]/used.sum()*100)}%)" for c in used.index)
    
    hold_pcts[yr] = {POOL.get(c,c): round(used[c]/used.sum()*100, 1) for c in used.index}
    
    print(f" {yr:>5} {nd:>6} {cagr:>7.1f}% {vol:>6.1f}% {wr:>6.1f}% {pr:>6.0f}% {yr_reb:>5}  {hold_str}")

# 全期
total_ret = ret
nd = len(total_ret)
total_cagr = round((eq.iloc[-1]**(252/nd)-1)*100, 1)
total_vol = round(np.sqrt(252)*total_ret.std()*100, 1)
total_wr = round((total_ret>0).sum()/nd*100, 1)
total_pr = round((pos.sum(axis=1)>0).mean()*100, 1)
total_reb = len(rebal_dates)
yr_pos = pos
tot_counts = yr_pos.sum(axis=0)
used = tot_counts[tot_counts > 0].sort_values(ascending=False)
hold_str = ", ".join(f"{POOL.get(c,c)}({round(used[c]/used.sum()*100)}%)" for c in used.index)
sp = round(np.sqrt(252)*total_ret.mean()/total_ret.std(), 2)
mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)

print("-"*100)
print(f" {'全期':>5} {nd:>6} {total_cagr:>7.1f}% {total_vol:>6.1f}% {total_wr:>6.1f}% {total_pr:>6.0f}% {total_reb:>5}  {hold_str}")
print(f"\n  夏普={sp}  最大回撤={mdd}%")

# 逐年持有标的详细表
print(f"\n{'='*100}")
print(f"    逐年ETF持仓占比明细")
print(f"{'='*100}")
print(f"{'年份':>6}", end="")
years = sorted(hold_pcts.keys())
etfs = sorted(set(c for y in years for c in hold_pcts[y].keys()))
for e in etfs:
    print(f"{POOL.get(e,e):>9}", end="")
print()
print("-"*100)
for yr in years:
    print(f" {yr:>5}", end="")
    for e in etfs:
        pct = hold_pcts[yr].get(e, 0)
        if pct >= 10:
            print(f" {pct:>7.1f}%", end="")
        elif pct > 0:
            print(f"   {pct:>.0f}%", end="")
        else:
            print(f" {'-':>9}", end="")
    print()

# 交易日志
print(f"\n{'='*100}")
print(f"    调仓日志 (共{len(rebal_dates)}次)")
print(f"{'='*100}")
print(f"{'日期':<14} {'买入':>10} {'前日RSRS':>10} {'备注'}")
print("-"*100)
prev_hr = 0
for i, (dt, target) in enumerate(rebal_dates):
    # Prev RSRS z-score
    zscore_val = round(float(zs_raw[min(len(zs_raw)-1, list(pd.to_datetime(df_sig["date"].values)).index(dt))]), 2) if dt in pd.to_datetime(df_sig["date"].values) else 0
    # Holdings between this and next rebalance
    next_dt = rebal_dates[i+1][0] if i+1 < len(rebal_dates) else ret.index[-1]
    hdays = len([d for d in ret.index if dt <= d < next_dt])
    print(f" {dt.date()!s:<14} {POOL.get(target,target):>10} {zscore_val:>10.2f} {hdays:>4}日持有")

print("="*100)
