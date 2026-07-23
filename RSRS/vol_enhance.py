"""
成交量增强回测：标的池10只固定
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}

# Load raw with volume
HIST = r"D:\QClaw_Trading\data\history"
raw_vol = {}
for code in POOL:
    with open(f"{HIST}\\{code}.json","r",encoding="utf-8") as f:
        d = json.load(f)
    df = pd.DataFrame(d["records"])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    raw_vol[code] = df[["close","vol"]]

# Build panel
dates = sorted(set(d for code in raw_vol for d in raw_vol[code].index))
panel = pd.DataFrame(index=dates)
for code in POOL:
    s = raw_vol[code]["close"]
    panel[code] = s.reindex(dates)

# Build momentum & volume indicators
mom63, vol_ma21, vol_ma63 = {}, {}, {}
for code, df in raw_vol.items():
    c = df["close"]
    v = df["vol"].fillna(0)
    mom63[code] = c.pct_change(63)
    vol_ma21[code] = v.rolling(21).mean()
    vol_ma63[code] = v.rolling(63).mean()

# Signal
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, 900, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

def run(mode="baseline", mom_w=63, lock=42):
    """
    mode options:
      "baseline"    - 原版: Top1正动量
      "vol_filter"  - 正动量中选量比最高
      "vol_weighted"- return * vol_ratio 排序
      "vol_confirm" - 动量正 + 量比>1, 否则不买
    """
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= 63:
            # Build candidate list
            cand = []
            for c in POOL:
                ok = True
                if dt not in mom63[c].index or np.isnan(mom63[c].loc[dt]): ok = False
                if not ok: continue
                mom = float(mom63[c].loc[dt])
                vol21 = float(vol_ma21[c].loc[dt]) if dt in vol_ma21[c].index else 0
                vol63 = float(vol_ma63[c].loc[dt]) if dt in vol_ma63[c].index else 1
                vol_ratio = vol21 / vol63 if vol63 > 0 else 1
                cand.append((c, mom, vol_ratio))
            
            if not cand: hold = []; continue
            # Filter positive momentum
            pos_cand = [x for x in cand if x[1] > 0]
            if not pos_cand: hold = []; continue
            
            if mode == "baseline":
                # Top1 by momentum
                pos_cand.sort(key=lambda x: -x[1])
                hold = [pos_cand[0][0]]
            elif mode == "vol_filter":
                # Of positive momentum ETFs, pick the one with highest vol_ratio
                pos_cand.sort(key=lambda x: -x[2])
                hold = [pos_cand[0][0]]
            elif mode == "vol_weighted":
                # Score = momentum * vol_ratio
                scored = [(c, m * vr) for c,m,vr in pos_cand]
                scored.sort(key=lambda x: -x[1])
                hold = [scored[0][0]]
            elif mode == "vol_confirm":
                # Only buy if vol_ratio > 1.0 (volume expanding)
                confirmed = [x for x in pos_cand if x[2] > 1.0]
                if confirmed:
                    confirmed.sort(key=lambda x: -x[1])
                    hold = [confirmed[0][0]]
                else:
                    hold = []  # No confirm, stay flat even if RSRS long
            
            lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[900])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        nd = m.sum()
        if nd < 5: continue
        annual[yr] = round(((1+ret[m]).cumprod().iloc[-1] - 1) * 100, 1)  # actual
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    pr = round((pos.sum(axis=1)>0).mean()*100, 1)
    vol = round(np.sqrt(252)*ret.std()*100, 1)
    total_ret = round((eq.iloc[-1] - 1) * 100, 1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"Vol":vol,"Pos%":pr,"Total":total_ret,"Annual":annual}

SEP = "="*95
print(SEP)
print("  成交量增强回测")
print(SEP)

modes = [
    ("原版(基线): 63d动量Top1", "baseline"),
    ("成交量筛选: 正动量中选量比最高的", "vol_filter"),
    ("量价加权: momentum*vol_ratio排序", "vol_weighted"),
    ("量确认: 只买量比>1的", "vol_confirm"),
]

for name, mode in modes:
    r = run(mode=mode)
    if r:
        print(f"\n  {name}")
        print(f"  全期: CAGR={r['CAGR']}%  Sharpe={r['Sharpe']}  MDD={r['MDD']}%  Calmar={r['Calmar']}  Vol={r['Vol']}%  仓位={r['Pos%']}%  总收益={r['Total']}%")
        if r['Annual']:
            ann = "  ".join(f"{yr}:{r['Annual'][yr]:>5.1f}%" for yr in sorted(r['Annual'].keys()))
            print(f"  年: {ann}")

# ═══ 同时改动量窗口测试 ═══
print(f"\n{SEP}")
print("  成交量筛选 + 不同动量窗口")
print(SEP)
from rsrs_final_strategy import load_etf as le2
raw2 = {}
for code in POOL:
    df = le2(code)
    s = df.set_index("date")["close"]
    raw2[code] = s[s.index.isin(panel.index)]

for mw in [21, 42, 63]:
    # Recompute momentum at this window
    m_mom = {}
    for code, df in raw_vol.items():
        m_mom[code] = df["close"].pct_change(mw)
    
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if 42 > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if 42 > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=42)
        if lr is None or (dt - lr).days >= 63:
            cand = []
            for c in POOL:
                if dt not in m_mom[c].index or np.isnan(m_mom[c].loc[dt]): continue
                mom = float(m_mom[c].loc[dt])
                vol21 = float(vol_ma21[c].loc[dt]) if dt in vol_ma21[c].index else 0
                vol63 = float(vol_ma63[c].loc[dt]) if dt in vol_ma63[c].index else 1
                vr = vol21/vol63 if vol63>0 else 1
                cand.append((c, mom, vr))
            if not cand: hold = []; continue
            pos_cand = [x for x in cand if x[1] > 0 and x[2] > 1.0]
            if pos_cand:
                pos_cand.sort(key=lambda x: -x[1])
                hold = [pos_cand[0][0]]
            else:
                hold = []
            lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[900])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: continue
    eq = (1 + ret).cumprod()
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    print(f"  量确认+mom={mw:>2}d: CAGR={cagr:>5.1f}% Sharpe={sp:.2f} MDD={mdd:>5.1f}% Calmar={calmar:.2f}")

# Volume filter + momentum 63 (no lock test)
print(f"\n{SEP}")
print("  成交量筛选 + 无锁/锁42对比")
print(SEP)
for lock_test in [0, 42]:
    for vr_thr in [0.8, 1.0, 1.2]:
        pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
        hold, lr, lku = [], None, None
        for dt in panel.index:
            if dt not in sig_s.index: continue
            raw_s = float(sig_s.loc[dt])
            eff = raw_s
            if lock_test > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
            if eff == 0: hold, lku = [], None; continue
            if lock_test > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock_test)
            if lr is None or (dt - lr).days >= 63:
                cand = []
                for c in POOL:
                    if dt not in mom63[c].index or np.isnan(mom63[c].loc[dt]): continue
                    mom = float(mom63[c].loc[dt])
                    vol21 = float(vol_ma21[c].loc[dt]) if dt in vol_ma21[c].index else 0
                    vol63 = float(vol_ma63[c].loc[dt]) if dt in vol_ma63[c].index else 1
                    vr = vol21/vol63 if vol63>0 else 1
                    cand.append((c, mom, vr))
                if not cand: hold = []; continue
                pos_cand = [x for x in cand if x[1] > 0 and x[2] > vr_thr]
                if pos_cand:
                    pos_cand.sort(key=lambda x: -x[1])
                    hold = [pos_cand[0][0]]
                else:
                    hold = []
                lr = dt
            if hold:
                w = float(sc.loc[dt]) if dt in sc.index else 1.0
                if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
        dr = panel.pct_change().fillna(0)
        ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
        fs = pd.to_datetime(df_sig["date"].iloc[900])
        ret = ret[ret.index >= fs]
        if len(ret) < 20: continue
        eq = (1 + ret).cumprod()
        cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
        sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
        mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
        calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
        print(f"  锁{lock_test:>2} 量比>{vr_thr:.1f}: CAGR={cagr:>5.1f}% Sharpe={sp:.2f} MDD={mdd:>5.1f}% Calmar={calmar:.2f}")

print(f"\n{SEP}")
print("  完成")
print(SEP)
