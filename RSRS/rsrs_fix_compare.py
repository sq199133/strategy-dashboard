"""
RSRS修正对比 - 用10只宽基池，用户指定的最终标的
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, r"D:\QClaw_Trading\RSRS")

# ── 覆写默认池为10只宽基 ──
import rsrs_final_strategy as strat
strat.DEFAULT_POOL = {
    "510050": "上证50", "510300": "沪深300", "510500": "中证500",
    "512100": "中证1000", "159915": "创业板指", "588000": "科创50",
    "513500": "标普500", "513100": "纳指ETF", "518880": "黄金ETF",
    "162411": "华宝油气"
}
DEFAULT_POOL = strat.DEFAULT_POOL

# 重新加载构建函数
from rsrs_final_strategy import (
    load_etf, build_panel, compute_momentum,
    compute_vol_scaling, run_strategy, analyze_performance
)

DATA_DIR = r'D:\QClaw_Trading\data\history'

# ── 加载数据 ──
print("Loading 10-ETF pool data...")
data, panel = build_panel(DEFAULT_POOL)
print(f"  {len(DEFAULT_POOL)} ETFs, {len(panel)} trading days")
print(f"  Range: {panel.index[0].date()} ~ {panel.index[-1].date()}")

# ── 沪深300 ──
with open(f"{DATA_DIR}\\510300.json","r",encoding="utf-8") as f:
    hs300 = json.load(f)
hs300 = pd.DataFrame(hs300["records"])
hs300["date"] = pd.to_datetime(hs300["date"])
high, low, close = hs300["high"].values, hs300["low"].values, hs300["close"].values
hs300_dates = hs300["date"].values
N, M = 18, 900

# ── 原版RSRS ──
def orig_rsrs():
    beta = np.full(len(hs300), np.nan)
    for i in range(N-1, len(hs300)):
        y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
        if not np.isnan(x).any() and not np.isnan(y).any():
            try: beta[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
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
    return sig, zs

# ── 方向乘数修正 ──
def signed_rsrs():
    beta = np.full(len(hs300), np.nan)
    for i in range(N-1, len(hs300)):
        y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
        if np.isnan(x).any() or np.isnan(y).any(): continue
        try:
            b = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
            beta[i] = b * (1 if close[i] >= close[i-N+1] else -1)
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
    return sig, zs

# ── 9+9分段检查（高点低点都在抬升）──
def seg9_rsrs():
    beta = np.full(len(hs300), np.nan)
    for i in range(N-1, len(hs300)):
        y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
        if np.isnan(x).any() or np.isnan(y).any(): continue
        front_high = max(y[:9]); back_high = max(y[9:])
        front_low = min(x[:9]); back_low = min(x[9:])
        if back_high > front_high and back_low > front_low:
            try: beta[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
            except: pass
        else:
            beta[i] = 0.0
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
    return sig, zs

print("Computing RSRS signals...")
sig1, zs1 = orig_rsrs()
sig2, zs2 = signed_rsrs()
sig3, zs3 = seg9_rsrs()

# ── 公共部分 ──
print("Computing momentum & vol scaling...")
mom_data = compute_momentum(data, panel)
df510 = load_etf('510300')
vol_scaling = compute_vol_scaling(df510, panel.index)

# ── 回测 ──
def backtest(signal_array, label):
    print(f"  Running {label}...")
    pos = run_strategy(data, panel, signal_array, hs300_dates,
                       mom_data, rebalance_days=42, top_n=1, vol_scaling=vol_scaling)
    annual_df, total_row, ret, stats = analyze_performance(panel, pos)
    return annual_df, total_row, stats

ann1, tot1, st1 = backtest(sig1, "Original")
ann2, tot2, st2 = backtest(sig2, "Signed(18d)")
ann3, tot3, st3 = backtest(sig3, "Seg9+9")

# ── 输出 ──
print("\n" + "="*90)
print("  RSRS修正对比（10只宽基池，实际策略框架）")
print(f"  标的: {', '.join(DEFAULT_POOL.values())}")
print("="*90)

schemes = [("原版", tot1), ("方向乘数(18d)", tot2), ("9+9分段抬升", tot3)]
print(f"\n  {'':26s} {'CAGR':>7s} {'Sharpe':>8s} {'MDD':>7s} {'持仓%':>6s}")
print(f"  {'-'*56}")
for name, t in schemes:
    print(f"  {name:<24s} {float(t['Strategy%']):>6.1f}% {float(t['Sharpe']):>7.2f} {float(t['MDD%']):>6.1f}% {st1['trade_days']/2107*100:>5.1f}%")

# 分年
yrs1 = {r['Year']: r for _, r in ann1.iterrows()}
yrs2 = {r['Year']: r for _, r in ann2.iterrows()}
yrs3 = {r['Year']: r for _, r in ann3.iterrows()}
all_yrs = sorted(set([int(k) for k in yrs1] + [int(k) for k in yrs2] + [int(k) for k in yrs3]))

print(f"\n  ──── 分年收益 ────")
print(f"  {'Year':<6s} {'原版%':>8s} {'方向乘数%':>10s} {'9+9分段%':>10s}")
for yr in all_yrs:
    s1 = yrs1[yr]['Strategy%'] if yr in yrs1 else 0
    s2 = yrs2[yr]['Strategy%'] if yr in yrs2 else 0
    s3 = yrs3[yr]['Strategy%'] if yr in yrs3 else 0
    print(f"  {yr:<6d} {s1:>7.1f}% {s2:>9.1f}% {s3:>9.1f}%")

print(f"\n" + "="*90)
