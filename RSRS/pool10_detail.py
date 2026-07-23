"""
10只新池 - 最佳方案(M=900 RB=63 锁42d) 详细分析
"""
import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL"}

raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

def run_detail(M=900, rb=63, lock=42, no_neg=True):
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
    zs_s = pd.Series(zs_raw, index=pd.to_datetime(df_sig["date"].values))
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0:
            eff = 1.0
        if eff == 0:
            hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None:
            lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= rb:
            scs = {}
            for c in POOL:
                if dt in mom[c].index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c,v in rk if v>0] if no_neg else [c for c,v in rk]
            hold = sel[:1] if sel else []; lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    eq = (1 + ret).cumprod()
    
    # 分年明细
    print(f"\n{'='*80}")
    print(f"  M={M}  RB={rb}  Lock={lock}")
    print(f"  全期: CAGR={round((eq.iloc[-1]**(252/len(ret))-1)*100,1)}%  ", end="")
    sp = np.sqrt(252)*ret.mean()/ret.std() if ret.std()>1e-10 else 0
    mdd = ((eq-eq.cummax())/eq.cummax()).min()
    calmar = round((eq.iloc[-1]**(252/len(ret))-1)*100/abs(mdd*100),2)
    print(f"Sharpe={round(sp,2)}  MDD={round(mdd*100,1)}%  Calmar={calmar}")
    print(f"{'='*80}")
    
    print(f"{'年份':>6} {'收益率':>8} {'年化波动':>8} {'胜率':>6} {'持仓日':>6} {'触发调仓':>6} 操作")
    print("-"*80)
    total_rebal = 0
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        nd = m.sum()
        if nd < 5: continue
        yr_ret = ret[m]
        yr_eq = (1 + yr_ret).cumprod()
        cagr_yr = round((yr_eq.iloc[-1]**(252/nd)-1)*100, 1)
        vol = round(np.sqrt(252)*yr_ret.std()*100, 1)
        wr = round((yr_yr:=(yr_ret>0).sum()/nd*100), 1)
        pr = round((pos.loc[yr_ret.index].sum(axis=1)>0).mean()*100, 1)
        
        # Count rebalances in this year
        reb = sum(1 for d in lr_dates if d.year == yr) if 'lr_dates' in dir() else 0
        total_rebal += reb
        
        print(f"{yr:>6} {cagr_yr:>7.1f}% {vol:>7.1f}% {wr:>5.1f}% {pr:>5.0f}% {reb:>5d}  ", end="")

    # 年化波动
    full_vol = round(np.sqrt(252)*ret.std()*100, 1)
    print(f"\n\n  年化波动率: {full_vol}%")
    print(f"  卡玛比率: {calmar}")
    
    # 持仓标的统计
    pos_counts = pos.sum(axis=0)
    used = pos_counts[pos_counts > 0].sort_values(ascending=False)
    print(f"\n  持仓标的分布:")
    total_pos = used.sum()
    for c, cnt in used.items():
        pct = cnt/total_pos*100
        print(f"    {c} ({POOL.get(c,'?')}): {cnt:.0f}天 ({pct:.1f}%)")
    
    # 胜负月
    monthly = ret.resample('ME').apply(lambda x: (1+x).prod()-1)
    win_m = (monthly > 0).sum()
    lose_m = (monthly < 0).sum()
    print(f"\n  月度胜率: {win_m}/{win_m+lose_m} = {round(win_m/(win_m+lose_m)*100,1)}%")

    return ret, eq, pos

# 最佳方案
ret, eq, pos = run_detail(900, 63, 42)

# 对比基线
print(f"\n\n{'='*80}")
print(f"  对比：3个候选方案")
print(f"{'='*80}")

results = {
    "Baseline (M=1200 RB=42 锁0)": (1200, 42, 0),
    "RB=63 锁42d (M=1200)": (1200, 63, 42),
    "最佳 (M=900 RB=63 锁42d)": (900, 63, 42),
}

for name, (M, rb, lock) in results.items():
    r = run_caller(M, rb, lock)
    
# Save final results
with open("D:\\QClaw_Trading\\RSRS\\pool10_best.json","w",encoding="utf-8") as f:
    json.dump({"final_strategy": {
        "pool": list(POOL.keys()),
        "N": 18, "M": 900, "buy": 0.7, "sell": -1.0,
        "RB": 63, "Lock": 42, "Top": 1, "Momentum": "63d single window",
        "VolScaling": {"VW": 70, "TV": 0.16}
    }}, f, ensure_ascii=False, indent=2)

print(f"\n  最终配置已保存")
