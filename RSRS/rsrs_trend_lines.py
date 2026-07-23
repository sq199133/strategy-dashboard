"""
RSRS 两条线正确逻辑：
用时间趋势替代回归原点

思路：每18天
  1. 对最高价做线性回归（high = a_h + b_h × time）
     → 得到一条"高线"（斜率b_h）
  2. 对最低价做线性回归（low = a_l + b_l × time）
     → 得到一条"低线"（斜率b_l）
  3. 两条线的关系 = 它们的方向一致性
     方案A: 斜率均值 (b_h + b_l)/2 → 涨正跌负
     方案B: 斜率积 b_h × b_l → 同向为正(涨跌都正)，异向为负(转折)
     方案C: 斜率符合同号 min(b_h, b_l) → 要求高线和低线同时确认趋势
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
vol_sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

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
            w = float(vol_sc.loc[dt]) if dt in vol_sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    nav = (1+ret).cumprod()
    annual_real = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        if m.sum() < 5: continue
        yr_ret = ret[m]
        annual_real[yr] = round(float((1+yr_ret).prod() - 1) * 100, 1)
    total_ret = round(float(nav.iloc[-1] - 1) * 100, 1)
    cagr = round((nav.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*float(ret.mean())/float(ret.std()),2) if float(ret.std())>1e-10 else 0
    mdd = round(float(((nav-nav.cummax())/nav.cummax()).min())*100, 1)
    return {"Total":total_ret,"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Annual":annual_real}

# ── 1. 原版RSRS ──
print("Computing...")
beta_orig = np.full(len(df_sig), np.nan)
for i in range(N-1, len(df_sig)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if not np.isnan(x).any() and not np.isnan(y).any():
        try: beta_orig[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        except: pass
zs_orig = np.full(len(beta_orig), np.nan)
for i in range(M-1, len(beta_orig)):
    v = beta_orig[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100: mu,sg=np.mean(vv),np.std(vv,ddof=1)
    if sg>0: zs_orig[i]=(beta_orig[i]-mu)/sg
sig_orig = np.zeros(len(zs_orig)); p=0
for i in range(len(zs_orig)):
    if not np.isnan(zs_orig[i]):
        if zs_orig[i]>0.7: p=1
        elif zs_orig[i]<-1.0: p=0
    sig_orig[i]=p
r_orig = backtest(sig_orig)
print(f"  原版: Total={r_orig['Total']}% CAGR={r_orig['CAGR']}% Sharpe={r_orig['Sharpe']}")

# ── 公共函数：计算两条趋势线 ──
def compute_trend_lines(win):
    """对每个窗口，分别对high和low做时间回归，返回斜率"""
    sh = np.full(len(df_sig), np.nan); sl = np.full(len(df_sig), np.nan)
    x_t = np.arange(win)
    for i in range(win-1, len(df_sig)):
        yh = high[i-win+1:i+1]; yl = low[i-win+1:i+1]
        if np.isnan(yh).any() or np.isnan(yl).any(): continue
        try:
            sh[i] = np.polyfit(x_t, yh, 1)[0]
            sl[i] = np.polyfit(x_t, yl, 1)[0]
        except: pass
    return sh, sl

def zscore_signal(values, thresh_up=0.7, thresh_dn=-1.0):
    """对任意值序列做M天z-score标准化 → 信号"""
    zs = np.full(len(values), np.nan)
    for i in range(M-1, len(values)):
        v = values[i-M+1:i+1]; vv=v[~np.isnan(v)]
        if len(vv)>=100: mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>1e-12: zs[i]=(values[i]-mu)/sg
    sig = np.zeros(len(zs)); p=0
    for i in range(len(zs)):
        if not np.isnan(zs[i]):
            if zs[i]>thresh_up: p=1
            elif zs[i]<thresh_dn: p=0
        sig[i]=p
    return sig

# ── 2. 平均斜率法：(b_h + b_l) / 2 ──
print("  方案A: 平均斜率...")
for win in [10, 18, 30]:
    for norm in [900]:
        sh, sl = compute_trend_lines(win)
        avg_slope = (sh + sl) / 2
        sig = zscore_signal(avg_slope)
        r = backtest(sig)
        if r:
            y22 = r['Annual'].get(2022, 0)
            print(f"    窗口{win}: Total={r['Total']}% Sharpe={r['Sharpe']} MDD={r['MDD']}% 2022={y22}%")

# ── 3. 斜率符号一致性法：斜率积 b_h × b_l ──
print("  方案B: 斜率积...")
for win in [10, 18, 30]:
    sh, sl = compute_trend_lines(win)
    prod = sh * sl
    sig = zscore_signal(prod)
    r = backtest(sig)
    if r:
        y22 = r['Annual'].get(2022, 0)
        print(f"    窗口{win}: Total={r['Total']}% Sharpe={r['Sharpe']} MDD={r['MDD']}% 2022={y22}%")

# ── 4. 取最小斜率（两线同时确认趋势）──
print("  方案C: min(b_h, b_l)...")
for win in [10, 18, 30]:
    sh, sl = compute_trend_lines(win)
    # 如果同号则取绝对值最小的（保守），异号则取负值（不看多）
    combo = np.full(len(sh), np.nan)
    for i in range(len(sh)):
        if np.isnan(sh[i]) or np.isnan(sl[i]): continue
        if sh[i] > 0 and sl[i] > 0:
            combo[i] = min(sh[i], sl[i])  # 都正→取小的（保守看多）
        elif sh[i] < 0 and sl[i] < 0:
            combo[i] = -abs(min(abs(sh[i]), abs(sl[i])))  # 都负→取小的（保守看空）
        else:
            combo[i] = 0  # 矛盾信号
    sig = zscore_signal(combo)
    r = backtest(sig)
    if r:
        y22 = r['Annual'].get(2022, 0)
        print(f"    窗口{win}: Total={r['Total']}% Sharpe={r['Sharpe']} MDD={r['MDD']}% 2022={y22}%")

# ── 5. 直接看close的趋势斜率（最简方案）──
print("  方案D: close趋势斜率...")
for win in [10, 18, 30, 60]:
    sc = np.full(len(df_sig), np.nan)
    x_t = np.arange(win)
    for i in range(win-1, len(df_sig)):
        y = close[i-win+1:i+1]
        if not np.isnan(y).any():
            try: sc[i] = np.polyfit(x_t, y, 1)[0]
            except: pass
    sig = zscore_signal(sc)
    r = backtest(sig)
    if r:
        y22 = r['Annual'].get(2022, 0)
        print(f"    窗口{win}: Total={r['Total']}% Sharpe={r['Sharpe']} MDD={r['MDD']}% 2022={y22}%")

# ── 6. 用高线在低线上方占比 % ──
print("  方案E: 高线高于低线的天数比率...")
for win in [18, 30]:
    # 不做时间回归，直接用每个窗口内 high>low 的天数
    ratio_hl = np.full(len(df_sig), np.nan)
    for i in range(win-1, len(df_sig)):
        hh = high[i-win+1:i+1]; ll = low[i-win+1:i+1]
        if np.isnan(hh).any() or np.isnan(ll).any(): continue
        ratio_hl[i] = np.sum(hh > ll) / win  # 应该总是1，因为high总是>low...
    # 这个没用

# ── 7. 残差法：high在当前窗口内偏离其趋势的程度 ──
print("  方案F: 高低点残差差...")
for win in [18]:
    sh, sl = compute_trend_lines(win)
    # 计算今天的预测值和真实值
    resid_h = np.full(len(df_sig), np.nan); resid_l = np.full(len(df_sig), np.nan)
    x_t = np.arange(win)
    for i in range(win-1, len(df_sig)):
        yh = high[i-win+1:i+1]; yl = low[i-win+1:i+1]
        if np.isnan(yh).any() or np.isnan(yl).any(): continue
        try:
            ah = np.polyfit(x_t, yh, 1); al = np.polyfit(x_t, yl, 1)
            pred_h = ah[0] * (win-1) + ah[1]; pred_l = al[0] * (win-1) + al[1]
        except: continue
        resid_h[i] = yh[-1] - pred_h; resid_l[i] = yl[-1] - pred_l
    # 残差差 = resid_h - resid_l
    resid_spread = resid_h - resid_l
    sig = zscore_signal(resid_spread)
    r = backtest(sig)
    if r:
        y22 = r['Annual'].get(2022, 0)
        print(f"    残差差: Total={r['Total']}% Sharpe={r['Sharpe']} MDD={r['MDD']}% 2022={y22}%")

print("\nDone.")
