"""
RSRS修正对比 — 用pool10_backtest.py的框架（RB=63, 锁42d），只改RSRS信号
"""
import sys, os, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
import sys
stdout_enc = getattr(sys.stdout, 'encoding', None)
if stdout_enc and stdout_enc.lower().startswith('gb'):
    sys.stdout.reconfigure(encoding='utf-8')

from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_vol_scaling

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL"}
N, M = 18, 900

# ── 加载数据 ──
print("Loading data...")
raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

def compute_rsrs_from_fn(fn, label=""):
    """使用给定函数计算RSRS信号"""
    high = df_sig["high"].values
    low = df_sig["low"].values
    close = df_sig["close"].values
    beta = np.full(len(df_sig), np.nan)
    for i in range(N - 1, len(df_sig)):
        y = high[i - N + 1:i + 1]
        x = low[i - N + 1:i + 1]
        if np.isnan(x).any() or np.isnan(y).any(): continue
        try:
            b = np.linalg.lstsq(np.column_stack([np.ones(N), x]), y, rcond=None)[0][1]
            beta[i] = fn(b, y, x, close[i - N + 1:i + 1])
        except: pass
    
    zs = np.full(len(beta), np.nan)
    for i in range(M - 1, len(beta)):
        v = beta[i - M + 1:i + 1]
        vv = v[~np.isnan(v)]
        if len(vv) >= 100:
            mu, sg = np.mean(vv), np.std(vv, ddof=1)
            if sg > 0:
                zs[i] = (beta[i] - mu) / sg
    
    sig = np.zeros(len(zs))
    pos = 0
    for i in range(len(zs)):
        if not np.isnan(zs[i]):
            if zs[i] > 0.7:
                pos = 1
            elif zs[i] < -1.0:
                pos = 0
        sig[i] = pos
    return sig, zs

# ── 回测引擎（取自 pool10_backtest.py）──
def backtest(sig_raw, rb=63, lock=42):
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
            cand = [(c, float(mom[c].loc[dt])) for c in POOL if dt in mom[c].index and not np.isnan(mom[c].loc[dt])]
            cand = [(c, v) for c, v in cand if v > 0]
            cand.sort(key=lambda x: -x[1])
            hold = [cand[0][0]] if cand else []
            lr = dt if hold else None
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        if m.sum() < 5: continue
        yr_eq = (1 + ret[m]).cumprod()
        annual[yr] = round((yr_eq.iloc[-1] ** (252 / m.sum()) - 1) * 100, 1)
    cagr = round((eq.iloc[-1] ** (252 / len(ret)) - 1) * 100, 1)
    sp = round(np.sqrt(252) * float(ret.mean()) / float(ret.std()), 2) if float(ret.std()) > 1e-10 else 0
    mdd = round(float(((eq - eq.cummax()) / eq.cummax()).min()) * 100, 1)
    return {"CAGR": cagr, "Sharpe": sp, "MDD": mdd, "Annual": annual}

# ── 构建不同的RSRS方案 ──

# 方案1: 原版
sig1, _ = compute_rsrs_from_fn(lambda b, y, x, c: b, "原版")

# 方案2: 方向乘数(18d close方向)
sig2, _ = compute_rsrs_from_fn(lambda b, y, x, c: b * (1 if c[-1] >= c[0] else -1), "方向乘数18d")

# 方案3: 9+9分段高低点抬升
def seg9_fn(b, y, x, c):
    back_high = max(y[9:]); front_high = max(y[:9])
    back_low = min(x[9:]); front_low = min(x[:9])
    return b if back_high > front_high and back_low > front_low else 0.0
sig3, _ = compute_rsrs_from_fn(seg9_fn, "9+9分段")

print("Running backtests (RB=63, 锁42d)...")
r1 = backtest(sig1, rb=63, lock=42)
r2 = backtest(sig2, rb=63, lock=42)
r3 = backtest(sig3, rb=63, lock=42)

# ── 输出 ──
print("\n" + "="*80)
print("  RSRS修正对比（10只宽基池，RB=63, 锁42d）")
print("="*80)

print(f"\n  {'':30s} {'原版':>12s} {'方向乘数':>12s} {'9+9分段':>12s}")
print(f"  {'-'*68}")
for k in ['CAGR', 'Sharpe', 'MDD']:
    v1 = r1[k]; v2 = r2[k]; v3 = r3[k]
    if k == 'Sharpe':
        print(f"  {k:<30s} {v1:>10.2f} {v2:>10.2f} {v3:>10.2f}")
    else:
        print(f"  {k:<30s} {v1:>9.1f}% {v2:>9.1f}% {v3:>9.1f}%")

all_yrs = sorted(set(list(r1['Annual'].keys()) + list(r2['Annual'].keys()) + list(r3['Annual'].keys())))
print(f"\n  ──── 分年收益 ────")
print(f"  {'Year':<6s} {'原版%':>8s} {'方向乘数%':>10s} {'9+9分段%':>10s}")
for yr in all_yrs:
    s1 = r1['Annual'].get(yr, 0)
    s2 = r2['Annual'].get(yr, 0)
    s3 = r3['Annual'].get(yr, 0)
    print(f"  {yr:<6d} {s1:>7.1f}% {s2:>9.1f}% {s3:>9.1f}%")

print(f"\n" + "="*80)
