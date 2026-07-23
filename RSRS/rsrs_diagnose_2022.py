"""
诊断：修正版RSRS的2022年异常收益来源
"""
import sys, os, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
sys.stdout.reconfigure(encoding='utf-8')
from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_vol_scaling

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL"}
N, M = 18, 900

raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

high = df_sig["high"].values; low = df_sig["low"].values
close = df_sig["close"].values

def calc_signal_and_pos(fn, label):
    beta = np.full(len(df_sig), np.nan)
    for i in range(N-1, len(df_sig)):
        y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
        if np.isnan(x).any() or np.isnan(y).any(): continue
        try:
            b = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
            beta[i] = fn(b, y, x, close[i-N+1:i+1])
        except: pass
    
    zs = np.full(len(beta), np.nan)
    for i in range(M-1, len(beta)):
        v = beta[i-M+1:i+1]; vv=v[~np.isnan(v)]
        if len(vv)>=100:
            mu,sg=np.mean(vv),np.std(vv,ddof=1)
            if sg>0: zs[i]=(beta[i]-mu)/sg
    
    sig = np.zeros(len(zs)); pos=0
    for i in range(len(zs)):
        if not np.isnan(zs[i]):
            if zs[i]>0.7: pos=1
            elif zs[i]<-1.0: pos=0
        sig[i]=pos
    
    # 回测
    sig_s = pd.Series(sig, index=pd.to_datetime(df_sig["date"].values))
    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt]); eff = raw_s
        if lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=42)
        if lr is None or (dt - lr).days >= 63:
            cand = [(c, float(mom[c].loc[dt])) for c in POOL if dt in mom[c].index and not np.isnan(mom[c].loc[dt])]
            cand = [(c, v) for c,v in cand if v>0]
            cand.sort(key=lambda x:-x[1])
            hold = [cand[0][0]] if cand else []; lr = dt if hold else None
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos_df.columns: pos_df.loc[dt, hold[0]] = w
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos_df.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    eq = (1+ret).cumprod()
    
    # 2022年明细
    m2022 = ret.index.year == 2022
    ret22 = ret[m2022]
    pos22 = pos_df.loc[m2022]
    
    # 持仓分布
    holdings_report = {}
    for c in pos22.columns:
        days = (pos22[c] > 0).sum()
        if days > 0: holdings_report[c] = days
    
    return {
        "sig": sig, "zs": zs,
        "ret22": ret22, "pos22": pos22,
        "holdings": holdings_report,
        "cagr22": round(((1+ret22).cumprod().iloc[-1]**(252/len(ret22))-1)*100,1),
        "ret_series": ret, "eq": eq
    }

# ── 原版 ──
r1 = calc_signal_and_pos(lambda b, y, x, c: b, "原版")
# ── 方向乘数 ──
r2 = calc_signal_and_pos(lambda b, y, x, c: b * (1 if c[-1] >= c[0] else -1), "方向乘数")
# ── 9+9 ──
r3 = calc_signal_and_pos(lambda b, y, x, c: b if max(y[9:])>max(y[:9]) and min(x[9:])>min(x[:9]) else 0.0, "9+9分段")

print("=" * 100)
print("  2022年持仓 & 收益明细诊断")
print("=" * 100)

labels = ["原版", "方向乘数", "9+9分段"]
results = [r1, r2, r3]

for label, r in zip(labels, results):
    print(f"\n── {label} ──")
    print(f"  2022年CAGR: {r['cagr22']}%")
    print(f"  持仓明细:")
    # 按月汇总回报
    ret22 = r['ret22']
    monthly = ret22.groupby(pd.Grouper(freq='ME')).apply(lambda x: (1+x).prod()-1)
    print(f"  月收益: ", "  ".join(f"{m.month}月:{v*100:+.1f}%" for m,v in monthly.items()))
    # 持仓
    print(f"  持仓ETF(天): ", {k: v for k,v in sorted(r['holdings'].items(), key=lambda x:-x[1])})
    # 看回撤
    eq = r['eq']
    mdd = ((eq.cummax() - eq) / eq.cummax()).max()
    print(f"  全年最大回撤: {mdd*100:.1f}%")

# 再看2022年初信号变化
print(f"\n── 2022-01 RSRS信号变化 ──")
print(f"{'Date':<12s} {'原zs':>8s} {'原sig':>6s} {'乘数zs':>8s} {'乘数sig':>6s} {'9+9zs':>8s} {'9+9sig':>6s} {'HS300':>8s}")
dates = pd.to_datetime(df_sig["date"].values)
for i in range(len(dates)):
    dt = dates[i]
    if dt.year != 2022 or dt.month > 2: continue
    if dt.month==1 or (dt.month==2 and dt.day<=10):
        z1 = r1['zs'][i] if i<len(r1['zs']) and not np.isnan(r1['zs'][i]) else None
        z2 = r2['zs'][i] if i<len(r2['zs']) and not np.isnan(r2['zs'][i]) else None
        z3 = r3['zs'][i] if i<len(r3['zs']) and not np.isnan(r3['zs'][i]) else None
        s1 = "L" if i<len(r1['sig']) and r1['sig'][i]==1 else "F"
        s2 = "L" if i<len(r2['sig']) and r2['sig'][i]==1 else "F"
        s3 = "L" if i<len(r3['sig']) and r3['sig'][i]==1 else "F"
        z1s = f"{z1:+.2f}" if z1 is not None else "N/A"
        z2s = f"{z2:+.2f}" if z2 is not None else "N/A"
        z3s = f"{z3:+.2f}" if z3 is not None else "N/A"
        hs300_close = df_sig.loc[df_sig['date']==pd.Timestamp(dt), 'close'].values
        hs_pct = f"{((hs300_close[0]/df_sig['close'].iloc[0]-1)*100):+.1f}%" if len(hs300_close)>0 and i>0 else ""
        print(f"  {str(dt.date()):<12s} {z1s:>8s} {s1:>6s} {z2s:>8s} {s2:>6s} {z3s:>8s} {s3:>6s}")
