"""
修正RSRS：高点低点都在上升才保留beta
对比原版RSRS回测结果
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}
HIST = r"D:\QClaw_Trading\data\history"

# ── 加载数据 ──
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

# ── 动量 ──
mom63 = {}
for code, df in raw.items():
    mom63[code]=df["close"].pct_change(63)

# ── 加载沪深300 ──
with open(f"{HIST}\\510300.json","r",encoding="utf-8") as f:
    hs300=json.load(f)
hs300=pd.DataFrame(hs300["records"])
hs300["date"]=pd.to_datetime(hs300["date"])
high, low, close = hs300["high"].values, hs300["low"].values, hs300["close"].values
hs300_dates = hs300["date"].values

N, M = 18, 900

# ── 原版RSRS ──
beta_orig = np.full(len(hs300), np.nan)
for i in range(N-1, len(hs300)):
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

sig_orig = np.zeros(len(zs_orig))
pos=0
for i in range(len(zs_orig)):
    if not np.isnan(zs_orig[i]):
        if zs_orig[i]>0.7: pos=1
        elif zs_orig[i]<-1.0: pos=0
    sig_orig[i]=pos

# ── 修正RSRS：9+9分段检查高低点是否都在抬升 ──
beta_fix = np.full(len(hs300), np.nan)
for i in range(N-1, len(hs300)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    c = close[i-N+1:i+1]
    if np.isnan(x).any() or np.isnan(y).any(): continue
    
    # 9+9分段
    front_high = max(y[:9]); back_high = max(y[9:])    # 前9天最高 vs 后9天最高
    front_low  = min(x[:9]); back_low  = min(x[9:])     # 前9天最低 vs 后9天最低
    
    # 高点在抬升 && 低点在抬升
    if back_high > front_high and back_low > front_low:
        try: beta_fix[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        except: pass
    else:
        beta_fix[i] = 0.0  # 不满足，直接归零

zs_fix = np.full(len(beta_fix), np.nan)
for i in range(M-1, len(beta_fix)):
    v = beta_fix[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs_fix[i]=(beta_fix[i]-mu)/sg

sig_fix = np.zeros(len(zs_fix))
pos=0
for i in range(len(zs_fix)):
    if not np.isnan(zs_fix[i]):
        if zs_fix[i]>0.7: pos=1
        elif zs_fix[i]<-1.0: pos=0
    sig_fix[i]=pos

# ── 波动率缩放 ──
hs300_close = hs300.set_index("date")["close"]
daily_ret = hs300_close.pct_change().fillna(0)
ann_vol = daily_ret.rolling(70).std() * np.sqrt(252)
scaling = (0.16/ann_vol).clip(0,1.0).fillna(1.0)

# ── 回测 ──
def backtest(panel, mom63, hs300_dates, signal_array, lock=42, label=""):
    sig_series = pd.Series(signal_array, index=pd.to_datetime(hs300_dates))
    sig_series = sig_series[sig_series.index.isin(panel.index)]
    
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    
    for dt in panel.index:
        if dt not in sig_series.index: continue
        raw_s = int(sig_series.loc[dt])
        eff = raw_s
        
        # 锁仓: 开多后lock天内不转空
        if lock > 0 and lku and dt <= lku and raw_s == 0:
            eff = 1
        if eff == 0:
            hold, lku = [], None
            continue
        if lock > 0 and raw_s == 1 and lku is None:
            lku = dt + pd.Timedelta(days=lock)
        
        # 调仓 (RB=63)
        if lr is None or (dt - lr).days >= 63:
            cand = []
            for c in POOL:
                if dt not in mom63[c].index or np.isnan(mom63[c].loc[dt]): continue
                m = float(mom63[c].loc[dt])
                if m > 0: cand.append((c,m))
            if cand:
                cand.sort(key=lambda x:-x[1])
                hold = [cand[0][0]]
                lr = dt
            else:
                hold = []
        
        if hold:
            w = float(scaling.loc[dt]) if dt in scaling.index else 1.0
            if hold[0] in pos.columns:
                pos.loc[dt,hold[0]] = w
    
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

SEP = "="*90
print(SEP)
print("  RSRS修正版 vs 原版 回测对比（10只池, 9+9分段高低点过滤）")
print(SEP)

orig = backtest(panel, mom63, hs300_dates, sig_orig, label="原版")
fixed = backtest(panel, mom63, hs300_dates, sig_fix, label="修正")

print(f"\n  {'':30s} {'原版RSRS':>12s} {'修正RSRS':>12s} {'差异':>8s}")
print(f"  {'-'*66}")
for k in ["CAGR","Sharpe","MDD","Calmar","Pos%","Total"]:
    ov = orig[k]; fv = fixed[k]
    if k == "Sharpe":
        diff = round(fv-ov,2)
        print(f"  {k:<30s} {ov:>10.2f} {fv:>10.2f} {diff:>+8.2f}")
    elif k == "Pos%":
        print(f"  {k:<30s} {ov:>9.1f}% {fv:>9.1f}% {fv-ov:>+7.1f}%")
    elif k == "MDD":
        print(f"  {k:<30s} {ov:>9.1f}% {fv:>9.1f}% {fv-ov:>+7.1f}%")
    elif k == "Calmar":
        print(f"  {k:<30s} {ov:>10.2f} {fv:>10.2f} {fv-ov:>+8.2f}")
    else:
        print(f"  {k:<30s} {ov:>9.1f}% {fv:>9.1f}% {fv-ov:>+7.1f}%")

print(f"\n  ──── 分年收益对比 ────")
all_years = sorted(set(list(orig["Annual"].keys()) + list(fixed["Annual"].keys())))
print(f"  {'Year':<8} {'原版%':>8} {'修正%':>8} {'差异':>8}")
for yr in all_years:
    ov = orig["Annual"].get(yr, 0)
    fv = fixed["Annual"].get(yr, 0)
    diff = fv - ov
    print(f"  {yr:<8d} {ov:>7.1f}% {fv:>7.1f}% {diff:>+7.1f}%")

# ── 查看修正版2026年以来的信号差异 ──
print(f"\n  ──── 2026年信号差异 ────")
print(f"  {'Date':<14} {'原z-score':>10} {'修z-score':>10} {'原sig':>6} {'修sig':>6}")
hs300_dates_dt = pd.to_datetime(hs300_dates)
for i in range(len(hs300_dates)):
    dt = hs300_dates_dt[i]
    if dt.year != 2026: continue
    zo = float(zs_orig[i]) if i < len(zs_orig) and not np.isnan(float(zs_orig[i])) else None
    zf = float(zs_fix[i]) if i < len(zs_fix) and not np.isnan(float(zs_fix[i])) else None
    so = "L" if i<len(sig_orig) and int(sig_orig[i])==1 else "F"
    sf = "L" if i<len(sig_fix) and int(sig_fix[i])==1 else "F"
    if zo is None and zf is None: continue
    zoom = f"{zo:+.2f}" if zo is not None else "N/A"
    zfm = f"{zf:+.2f}" if zf is not None else "N/A"
    print(f"  {str(dt.date()):<14} {zoom:>10} {zfm:>10} {so:>6} {sf:>6}")

print(f"\n{SEP}")
print("  完成")
print(SEP)
