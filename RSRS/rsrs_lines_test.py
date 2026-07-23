"""
将最高价和最低价各自变成一条线，看两条线之间的关系
三种思路：
  1. 趋势线斜率法：对high做线性回归得到斜率，对low做线性回归得到斜率，看斜率比
  2. 价格通道法：MA(high) - MA(low)，取宽度作为信号
  3. 对齐平滑法：MA=18与回归窗口对齐，再回归
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
    mdd = round(float(((eq - eq.cummax())/eq.cummax()).min())*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    wr = round((ret>0).mean()*100, 1)
    pos_pct = round((pos.sum(axis=1)>0).mean()*100, 1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"W%":wr,"Pos%":pos_pct,"Annual":annual}

# ── 基线：原版RSRS ──
print("Original RSRS...")
beta_orig = np.full(len(df_sig), np.nan)
for i in range(N-1, len(df_sig)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if not np.isnan(x).any() and not np.isnan(y).any():
        try: beta_orig[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        except: pass
zs_orig = np.full(len(beta_orig), np.nan)
for i in range(M-1, len(beta_orig)):
    v = beta_orig[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs_orig[i]=(beta_orig[i]-mu)/sg
sig_orig = np.zeros(len(zs_orig)); pos=0
for i in range(len(zs_orig)):
    if not np.isnan(zs_orig[i]):
        if zs_orig[i]>0.7: pos=1
        elif zs_orig[i]<-1.0: pos=0
    sig_orig[i]=pos
r_orig = backtest(sig_orig)

print("="*100)
results = {}

# ══════════════════════════════════════════════
# 思路1：趋势线斜率法
# 对high做线性回归（相对时间）得到斜率，对low同理
# 信号 = high_slope / low_slope 或 (high_slope - low_slope)
# ══════════════════════════════════════════════
print("\n[思路1] 趋势线斜率法")
for win_size in [10, 18, 30, 60]:
    slope_h = np.full(len(df_sig), np.nan)
    slope_l = np.full(len(df_sig), np.nan)
    for i in range(win_size-1, len(df_sig)):
        x_time = np.arange(win_size)
        yh = high[i-win_size+1:i+1]; yl = low[i-win_size+1:i+1]
        if np.isnan(yh).any() or np.isnan(yl).any(): continue
        try:
            slope_h[i] = np.polyfit(x_time, yh, 1)[0]
            slope_l[i] = np.polyfit(x_time, yl, 1)[0]
        except: pass
    
    # 用斜率比：high_slope / low_slope（两者都正=上涨；都负=下跌但比值可能正；一正一负=比值负=异常）
    ratio = np.full(len(slope_h), np.nan)
    for i in range(len(slope_h)):
        if not np.isnan(slope_h[i]) and not np.isnan(slope_l[i]) and abs(slope_l[i]) > 1e-12:
            ratio[i] = slope_h[i] / slope_l[i]
    
    zs = np.full(len(ratio), np.nan)
    for i in range(M-1, len(ratio)):
        v = ratio[i-M+1:i+1]; vv=v[~np.isnan(v)]
        if len(vv)>=100:
            mu,sg=np.mean(vv),np.std(vv,ddof=1)
            if sg>0: zs[i]=(ratio[i]-mu)/sg
    
    sig = np.zeros(len(zs)); pos=0
    for i in range(len(zs)):
        if not np.isnan(zs[i]):
            if zs[i]>0.7: pos=1
            elif zs[i]<-1.0: pos=0
        sig[i]=pos
    
    r = backtest(sig)
    name = f"斜率{win_size}"
    results[name] = r
    if r:
        yd = r['Annual'].get(2022, 0)
        print(f"  {name:<12s} CAGR={r['CAGR']:>5.1f}% Sharpe={r['Sharpe']:.2f} MDD={r['MDD']:>5.1f}% 2022={yd:>6.1f}%")

# ══════════════════════════════════════════════
# 思路2：价格通道宽度法
# MA(high) - MA(low)，取宽度作为信号
# 宽度扩大=上涨，宽度缩小=下跌
# ══════════════════════════════════════════════
print("\n[思路2] 价格通道宽度法")
def sma(arr, w):
    out = np.full_like(arr, np.nan)
    cs = np.cumsum(np.nan_to_num(arr))
    for i in range(w-1, len(arr)):
        out[i] = (cs[i] - (cs[i-w] if i>=w else 0)) / w
    return out

for ch_win in [18, 30, 60]:
    for norm_win in [900]:
        mh = sma(high, ch_win)
        ml = sma(low, ch_win)
        width = np.full(len(mh), np.nan)
        for i in range(len(mh)):
            if not np.isnan(mh[i]) and not np.isnan(ml[i]) and ml[i] > 1e-10:
                width[i] = (mh[i] - ml[i]) / ml[i] * 100
        
        zs = np.full(len(width), np.nan)
        for i in range(norm_win-1, len(width)):
            v = width[i-norm_win+1:i+1]; vv=v[~np.isnan(v)]
            if len(vv)>=100:
                mu,sg=np.mean(vv),np.std(vv,ddof=1)
                if sg>0: zs[i]=(width[i]-mu)/sg
        
        sig = np.zeros(len(zs)); pos=0
        for i in range(len(zs)):
            if not np.isnan(zs[i]):
                if zs[i]>0.7: pos=1
                elif zs[i]<-1.0: pos=0
            sig[i]=pos
        
        r = backtest(sig)
        name = f"通道{ch_win}"
        results[name] = r
        if r:
            yd = r['Annual'].get(2022, 0)
            print(f"  MA={ch_win:<3d} {norm_win:<4d}  CAGR={r['CAGR']:>5.1f}% Sharpe={r['Sharpe']:.2f} MDD={r['MDD']:>5.1f}% 2022={yd:>6.1f}%")

# ══════════════════════════════════════════════
# 思路3：对齐平滑法 - MA=18，再在原框架跑
# ══════════════════════════════════════════════
print("\n[思路3] 对齐平滑 (MA=18, N=18)")
mh18 = sma(high, 18)
ml18 = sma(low, 18)
beta18 = np.full(len(df_sig), np.nan)
for i in range(N-1, len(df_sig)):
    y = mh18[i-N+1:i+1]; x = ml18[i-N+1:i+1]
    if np.isnan(x).any() or np.isnan(y).any(): continue
    try: beta18[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
    except: pass
zs18 = np.full(len(beta18), np.nan)
for i in range(M-1, len(beta18)):
    v = beta18[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs18[i]=(beta18[i]-mu)/sg
sig18 = np.zeros(len(zs18)); pos=0
for i in range(len(zs18)):
    if not np.isnan(zs18[i]):
        if zs18[i]>0.7: pos=1
        elif zs18[i]<-1.0: pos=0
    sig18[i]=pos
r18 = backtest(sig18)
results["对齐MA=18"] = r18
if r18:
    print(f"  CAGR={r18['CAGR']:>5.1f}% Sharpe={r18['Sharpe']:.2f} MDD={r18['MDD']:>5.1f}%")

# ══════════════════════════════════════════════
# 思路4：只做一条线，用high-low价差/close的z-score
# ══════════════════════════════════════════════
print("\n[思路4] H-L差值/收盘价")
hl_ratio = np.full(len(df_sig), np.nan)
for i in range(len(df_sig)):
    if close[i] > 1e-10:
        hl_ratio[i] = (high[i] - low[i]) / close[i] * 100

for sm_win in [1, 5, 18]:
    if sm_win == 1:
        hl_smooth = hl_ratio.copy()
    else:
        hl_smooth = sma(hl_ratio, sm_win)
    
    zs = np.full(len(hl_smooth), np.nan)
    for i in range(M-1, len(hl_smooth)):
        v = hl_smooth[i-M+1:i+1]; vv=v[~np.isnan(v)]
        if len(vv)>=100:
            mu,sg=np.mean(vv),np.std(vv,ddof=1)
            if sg>0: zs[i]=(hl_smooth[i]-mu)/sg
    
    sig = np.zeros(len(zs)); pos=0
    for i in range(len(zs)):
        if not np.isnan(zs[i]):
            if zs[i]>0.7: pos=1
            elif zs[i]<-1.0: pos=0
        sig[i]=pos
    
    r = backtest(sig)
    name = f"HL比_SMA{sm_win}"
    results[name] = r
    if r:
        print(f"  SMA={sm_win:<2d}  CAGR={r['CAGR']:>5.1f}% Sharpe={r['Sharpe']:.2f} MDD={r['MDD']:>5.1f}%")

# ── 总对比 ──
print("\n" + "="*100)
print("  最终对比")
print("="*100)
print(f"\n  {'方法':<16s} {'CAGR':>7s} {'Sharpe':>7s} {'MDD':>7s} {'Calmar':>7s} {'2022':>7s} {'2024':>7s} {'2025':>7s}")
print(f"  {'-'*75}")
all_results = [("原版RSRS", r_orig)] + [(k, results[k]) for k in sorted(results.keys()) if results[k]]
for name, r in all_results:
    yd22 = r['Annual'].get(2022, 0)
    yd24 = r['Annual'].get(2024, 0)
    yd25 = r['Annual'].get(2025, 0)
    calmar = round(r['CAGR']/abs(r['MDD']), 2) if r['MDD'] < 0 else 0
    print(f"  {name:<16s} {r['CAGR']:>5.1f}% {r['Sharpe']:>6.2f} {r['MDD']:>5.1f}% {calmar:>6.2f} {yd22:>5.1f}% {yd24:>5.1f}% {yd25:>5.1f}%")

print("\n" + "="*100)
