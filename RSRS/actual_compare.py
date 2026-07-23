"""
实际收益对比：年化 vs 实际
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

mom_cache = {}
for code, df in raw.items():
    cdf = df.set_index("date")["close"]
    mc = {}
    for w in [21, 63]:
        mc[w] = cdf.pct_change(w)[cdf.pct_change(w).index.isin(panel.index)]
    mom_cache[code] = mc

def run(M=900, buy=0.7, sell=-1.0, rb=63, lock=42, mom_w=63):
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
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
                if dt in mom_cache[c][mom_w].index:
                    v = float(mom_cache[c][mom_w].loc[dt])
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c,v in rk if v>0]
            hold = sel[:1] if sel else []; lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    eq = (1 + ret).cumprod()
    return ret, eq, pos

# Run both strategies
ret1, eq1, pos1 = run(900, 0.7, -1.0, 63, 42, 63)       # 基线
ret2, eq2, pos2 = run(900, 0.5, -1.0, 63, 0, 21)         # 新方案(无锁)

SEP = "="*95
print(SEP)
print("    基线 (buy=0.7 mom=63 锁42) vs 新方案 (buy=0.5 mom=21 无锁)")
print(f"    全期 CAGR: {round((eq1.iloc[-1]**(252/len(ret1))-1)*100,1)}% vs {round((eq2.iloc[-1]**(252/len(ret2))-1)*100,1)}%")
print(SEP)

print(f"\n{'年份':>6} {'天数':>5} {'基线实际':>10} {'新方案实际':>10} {'基线CAGR':>10} {'新方案CAGR':>10} {'新方案持仓':>10}")
print("-"*95)

total1_act, total2_act = 1.0, 1.0
for yr in sorted(set(list(d.year for d in ret1.index) + list(d.year for d in ret2.index))):
    m1 = ret1.index.year == yr
    m2 = ret2.index.year == yr
    nd1, nd2 = m1.sum(), m2.sum()
    if nd1 < 5 and nd2 < 5: continue
    
    if nd1 >= 5:
        yr_ret1 = ret1[m1]
        yr_act1 = round(((1+yr_ret1).cumprod().iloc[-1] - 1) * 100, 1)
        yr_cagr1 = round(((1+yr_act1/100)**(252/nd1)-1)*100, 1) if nd1 > 5 else 0
        yr_pr1 = round((pos1.loc[yr_ret1.index].sum(axis=1)>0).mean()*100, 1)
        total1_act *= (1 + yr_act1/100)
    else:
        yr_act1, yr_cagr1, yr_pr1 = "-", "-", "-"
    
    if nd2 >= 5:
        yr_ret2 = ret2[m2]
        yr_act2 = round(((1+yr_ret2).cumprod().iloc[-1] - 1) * 100, 1)
        yr_cagr2 = round(((1+yr_act2/100)**(252/nd2)-1)*100, 1) if nd2 > 5 else 0
        yr_pr2 = round((pos2.loc[yr_ret2.index].sum(axis=1)>0).mean()*100, 1)
        total2_act *= (1 + yr_act2/100)
    else:
        yr_act2, yr_cagr2, yr_pr2 = "-", "-", "-"
    
    nd = max(nd1, nd2)
    print(f" {yr:>5} {nd:>5} {str(yr_act1):>9}% {str(yr_act2):>9}% {str(yr_cagr1):>9}% {str(yr_cagr2):>9}% {str(yr_pr2):>9}%")

# 全期
total1 = round((total1_act - 1)*100, 1)
total2 = round((total2_act - 1)*100, 1)
nd = len(ret1)
cagr1 = round(((1+total1/100)**(252/nd)-1)*100, 1)
nd2 = len(ret2)
cagr2 = round(((1+total2/100)**(252/nd2)-1)*100, 1)

print("-"*95)
print(f" {'全期':>5} {nd:>5} {total1:>9.1f}% {total2:>9.1f}% {cagr1:>9.1f}% {cagr2:>9.1f}%")

# 新方案 equity curve
fig_data = []
eq2_vals = [round(v, 6) for v in eq2.values]
dates = [str(d.date()) for d in eq2.index]
print(f"\n新方案净值曲线(每半年):")
for i in range(0, len(eq2), max(1, len(eq2)//20)):
    print(f"  {dates[i]}  1.0 -> {eq2_vals[i]:.4f}")
print(f"  {dates[-1]}  1.0 -> {eq2_vals[-1]:.4f}")

# 回撤分析
dd2 = (eq2 - eq2.cummax()) / eq2.cummax() * 100
max_dd_idx = dd2.idxmin()
print(f"\n最大回撤: {dd2.min():.1f}% (发生在 {max_dd_idx.date()})")

# 看最近持仓标的
latest = panel.index[-1]
active = pos2.loc[latest][pos2.loc[latest] > 0]
print(f"\n最新持仓: ", end="")
if len(active) > 0:
    print(f"{POOL[active.index[0]]} ({active.index[0]}) 仓位={float(active.iloc[0])*100:.0f}%")
else:
    print("空仓")

# 看2024年实际表现
m24 = ret2.index.year == 2024
ret24 = ret2[m24]
act24 = round(((1+ret24).cumprod().iloc[-1] - 1) * 100, 1)
print(f"\n2024年实际: {act24}%  (年化: {round(((1+act24/100)**(252/len(ret24))-1)*100,1)}%)")
