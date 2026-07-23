"""
RSRS修正对比：方向乘数修复 vs 原版
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}
HIST = r"D:\QClaw_Trading\data\history"

raw = {}
for code in POOL:
    with open(f"{HIST}\\{code}.json","r",encoding="utf-8") as f:
        d = json.load(f)
    df = pd.DataFrame(d["records"])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date",inplace=True)
    raw[code] = df

dates = sorted(set(d for code in raw for d in raw[code].index))
panel = pd.DataFrame(index=dates)
for code in POOL:
    panel[code] = raw[code]["close"].reindex(dates)

mom63 = {}
for code,df in raw.items():
    mom63[code]=df["close"].pct_change(63)

with open(f"{HIST}\\510300.json","r",encoding="utf-8") as f:
    hs300=json.load(f)
hs300=pd.DataFrame(hs300["records"])
hs300["date"]=pd.to_datetime(hs300["date"])
high, low, close = hs300["high"].values, hs300["low"].values, hs300["close"].values
hs300_dates = hs300["date"].values

N, M = 18, 900

def run_rsrs(beta_modify_fn=None):
    """通用的RSRS计算，beta_modify_fn接受(beta, high_slice, low_slice, close_slice)返回修正后的beta"""
    beta = np.full(len(hs300), np.nan)
    for i in range(N-1, len(hs300)):
        y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
        if np.isnan(x).any() or np.isnan(y).any(): continue
        try:
            b = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
            if beta_modify_fn:
                c = close[i-N+1:i+1]
                b = beta_modify_fn(b, y, x, c)
            beta[i] = b
        except: pass

    zs = np.full(len(beta), np.nan)
    for i in range(M-1, len(beta)):
        v = beta[i-M+1:i+1]; vv=v[~np.isnan(v)]
        if len(vv)>=100:
            mu,sg=np.mean(vv),np.std(vv,ddof=1)
            if sg>0: zs[i]=(beta[i]-mu)/sg

    sig = np.zeros(len(zs))
    pos=0
    for i in range(len(zs)):
        if not np.isnan(zs[i]):
            if zs[i]>0.7: pos=1
            elif zs[i]<-1.0: pos=0
        sig[i]=pos
    return sig, zs, beta

hs300_close_s = hs300.set_index("date")["close"]
daily_ret = hs300_close_s.pct_change().fillna(0)
ann_vol = daily_ret.rolling(70).std() * np.sqrt(252)
scaling = (0.16/ann_vol).clip(0,1.0).fillna(1.0)

def backtest(panel, mom63, hs300_dates, signal_array, lock=42):
    sig_series = pd.Series(signal_array, index=pd.to_datetime(hs300_dates))
    sig_series = sig_series[sig_series.index.isin(panel.index)]
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_series.index: continue
        raw_s = int(sig_series.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1
        if eff == 0: hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= 63:
            cand = []
            for c in POOL:
                if dt not in mom63[c].index or np.isnan(mom63[c].loc[dt]): continue
                m = float(mom63[c].loc[dt])
                if m > 0: cand.append((c,m))
            if cand:
                cand.sort(key=lambda x:-x[1])
                hold = [cand[0][0]]; lr = dt
            else: hold = []
        if hold:
            w = float(scaling.loc[dt]) if dt in scaling.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt,hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(hs300_dates)[M]
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1+ret).cumprod()
    annual={}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year==yr
        if m.sum()<5: continue
        annual[yr] = round(((1+ret[m]).cumprod().iloc[-1]-1)*100,1)
    total = round((eq.iloc[-1]-1)*100,1)
    nd = len(ret)
    cagr = round((eq.iloc[-1]**(252/nd)-1)*100,1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(),2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100,1)
    calmar = round(cagr/abs(mdd),2) if mdd<0 else 0
    pos_pct = round((pos.sum(axis=1)>0).mean()*100,1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"Pos%":pos_pct,"Total":total,"Annual":annual}

# ── 方案1: 原版 ──
sig1, zs1, _ = run_rsrs()
r1 = backtest(panel, mom63, hs300_dates, sig1)

# ── 方案2: 方向乘数(18天close方向) ──
sig2, zs2, _ = run_rsrs(beta_modify_fn=lambda b,y,x,c: b * (1 if c[-1] >= c[0] else -1))
r2 = backtest(panel, mom63, hs300_dates, sig2)

# ── 方案3: 方向乘数(63天close方向 - 与动量同步) ──
# 用63d方向是因为动量也是63d, 更一致
sig3, zs3, _ = run_rsrs(beta_modify_fn=lambda b,y,x,c: None)

# Need close 63d data separately for this
close_all = hs300["close"].values
def beta_signed_63d(b, y, x, c):
    global close_all
    i = hs300_dates.searchsorted(str(c.index[-1])[:10]) if hasattr(c, 'index') else -1
    # simpler: just compare current close with 63d ago
    return None

# Actually simpler to compute separately
print("Computing 63d-direction RSRS...")
beta_s63 = np.full(len(hs300), np.nan)
for i in range(N-1, len(hs300)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if np.isnan(x).any() or np.isnan(y).any(): continue
    try:
        b = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        # Use close change over 63 days for direction
        dir_idx = max(0, i-63)
        direction = 1 if close[i] >= close[dir_idx] else -1
        beta_s63[i] = b * direction
    except: pass

zs_s63 = np.full(len(beta_s63), np.nan)
for i in range(M-1, len(beta_s63)):
    v = beta_s63[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs_s63[i]=(beta_s63[i]-mu)/sg

sig_s63 = np.zeros(len(zs_s63))
pos=0
for i in range(len(zs_s63)):
    if not np.isnan(zs_s63[i]):
        if zs_s63[i]>0.7: pos=1
        elif zs_s63[i]<-1.0: pos=0
    sig_s63[i]=pos
r3 = backtest(panel, mom63, hs300_dates, sig_s63)

# ── 输出 ──
SEP = "="*90
print(SEP)
print("  RSRS修正对比")
print(SEP)

schemes = [
    ("原版(无修正)", r1),
    ("方向乘数(18d close方向)", r2),
    ("方向乘数(63d close方向)", r3),
]

print(f"\n  {'':42s} {'CAGR':>7s} {'Sharpe':>8s} {'MDD':>7s} {'Calmar':>7s} {'仓位':>6s}")
print(f"  {'-'*85}")
for name, r in schemes:
    if r:
        print(f"  {name:<40s} {r['CAGR']:>6.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>6.1f}% {r['Calmar']:>6.2f} {r['Pos%']:>5.1f}%")

print(f"\n  ──── 分年收益 ────")
print(f"  {'Year':<6s}", end="")
for name, _ in schemes: print(f" {name[:8]:>8s}", end="")
print()
for yr in sorted(set(list(r1["Annual"].keys()))):
    print(f"  {yr:<6d}", end="")
    for _, r in schemes:
        v = r["Annual"].get(yr, 0)
        print(f" {v:>7.1f}%", end="")
    print()
print()

# 只看2022年（市场下跌年）的信号差异
print(f"  ──── 2022年信号对比(市场下跌年) ────")
print(f"  {'Date':<12s} {'原版zs':>8s} {'18d方向zs':>10s} {'63d方向zs':>10s} {'原版sig':>8s} {'18d':>5s} {'63d':>5s}")
for i in range(len(hs300_dates)):
    dt = pd.to_datetime(hs300_dates[i])
    if dt.year != 2022: continue
    z1 = float(zs1[i]) if i<len(zs1) and not np.isnan(float(zs1[i])) else None
    z2 = float(zs2[i]) if i<len(zs2) and not np.isnan(float(zs2[i])) else None
    z3 = float(zs3[i]) if i<len(zs3) and not np.isnan(float(zs3[i])) else None
    s1 = "L" if i<len(sig1) and int(sig1[i])==1 else "F"
    s2 = "L" if i<len(sig2) and int(sig2[i])==1 else "F"
    s3 = "L" if i<len(sig3) and int(sig3[i])==1 else "F"
    if z1 is None and z2 is None and z3 is None: continue
    z1s = f"{z1:+.2f}" if z1 is not None else "N/A"
    z2s = f"{z2:+.2f}" if z2 is not None else "N/A"
    z3s = f"{z3:+.2f}" if z3 is not None else "N/A"
    print(f"  {str(dt.date()):<12s} {z1s:>8s} {z2s:>10s} {z3s:>10s} {s1:>8s} {s2:>5s} {s3:>5s}")
    if dt.month == 12: break  # enough data

print(f"\n{SEP}")
print("  完成")
print(SEP)
