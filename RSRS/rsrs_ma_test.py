"""
RSRS MA平滑版：用最高价/最低价的移动平均替代原始值做回归
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

high = df_sig["high"].values.astype(float)
low = df_sig["low"].values.astype(float)
close = df_sig["close"].values

def run_rsrs_ma(ma_window):
    """
    MA平滑版RSRS：
    用MA(high)和MA(low)代替原始high/low做回归
    """
    # 计算MA平滑值
    def ma(arr, w):
        out = np.full_like(arr, np.nan)
        cs = np.cumsum(np.nan_to_num(arr))
        for i in range(w-1, len(arr)):
            out[i] = (cs[i] - (cs[i-w] if i>=w else 0)) / w
        return out
    
    high_sm = ma(high, ma_window)
    low_sm = ma(low, ma_window)
    
    beta = np.full(len(df_sig), np.nan)
    for i in range(N-1, len(df_sig)):
        y = high_sm[i-N+1:i+1]
        x = low_sm[i-N+1:i+1]
        if np.isnan(x).any() or np.isnan(y).any(): continue
        try:
            beta[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
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
    return sig, zs, beta

def backtest(sig_raw, rb=63, lock=42):
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt]); eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= rb:
            cand = [(c, float(mom[c].loc[dt])) for c in POOL if dt in mom[c].index and not np.isnan(mom[c].loc[dt])]
            cand = [(c, v) for c,v in cand if v>0]
            cand.sort(key=lambda x:-x[1])
            hold = [cand[0][0]] if cand else []; lr = dt if hold else None
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1+ret).cumprod()
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        if m.sum() < 5: continue
        yr_eq = (1+ret[m]).cumprod()
        annual[yr] = round((yr_eq.iloc[-1]**(252/m.sum())-1)*100, 1)
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*float(ret.mean())/float(ret.std()),2) if float(ret.std())>1e-10 else 0
    mdd = round(float(((eq - eq.cummax()) / eq.cummax()).min())*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    wr = round((ret>0).mean()*100, 1)
    pos_pct = round((pos.sum(axis=1)>0).mean()*100, 1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"W%":wr,"Pos%":pos_pct,"Annual":annual}

# ── 原版 ──
print("Original RSRS...")
sig_orig, _, _ = run_rsrs_ma(1)  # MA=1 就是原始值
r_orig = backtest(sig_orig)

# ── MA平滑版 ──
ma_windows = [3, 5, 10, 15, 20, 30, 60]
results = {}
for w in ma_windows:
    print(f"  MA={w}...")
    sig, zs, betas = run_rsrs_ma(w)
    r = backtest(sig)
    results[w] = r

# ── 输出 ──
print("\n" + "="*90)
print("  RSRS MA平滑版（10只宽基池，RB=63, 锁42d）")
print("="*90)

print(f"\n  {'MA窗口':<8s} {'CAGR':>7s} {'Sharpe':>7s} {'MDD':>7s} {'Calmar':>7s} {'胜率':>6s} {'持仓':>6s}")
print(f"  {'-'*52}")
print(f"  {'原版(1)':<8s} {r_orig['CAGR']:>5.1f}% {r_orig['Sharpe']:>6.2f} {r_orig['MDD']:>5.1f}% {r_orig['Calmar']:>6.2f} {r_orig['W%']:>5.1f}% {r_orig['Pos%']:>5.1f}%")
for w in ma_windows:
    r = results[w]
    if r:
        print(f"  {'MA='+str(w):<8s} {r['CAGR']:>5.1f}% {r['Sharpe']:>6.2f} {r['MDD']:>5.1f}% {r['Calmar']:>6.2f} {r['W%']:>5.1f}% {r['Pos%']:>5.1f}%")

# 最好和最差的分年对比
best = max(results, key=lambda w: results[w]['Calmar'] if results[w] else -999)
print(f"\n  ──── 分年对比（原版 vs MA={best}）────")
print(f"  {'Year':<6s} {'原版%':>8s} {f'MA={best}%':>9s} {'差异':>8s}")
yrs_orig = r_orig['Annual']
yrs_best = results[best]['Annual']
for yr in sorted(set(list(yrs_orig.keys()) + list(yrs_best.keys()))):
    s1 = yrs_orig.get(yr, 0); s2 = yrs_best.get(yr, 0)
    print(f"  {yr:<6d} {s1:>7.1f}% {s2:>8.1f}% {s2-s1:>+7.1f}%")

# 2022年检查
print(f"\n  ──── 2022年诊断（各版本）────")
print(f"  {'版本':<10s} {'CAGR%':>8s}")
for label, rr in [("原版", r_orig)] + [("MA="+str(w), results[w]) for w in ma_windows]:
    if rr and rr['Annual'].get(2022):
        print(f"  {label:<10s} {rr['Annual'][2022]:>7.1f}%")
    elif rr:
        print(f"  {label:<10s} {'N/A':>8s}")

print(f"\n" + "="*90)
