"""
剔除黄金，重测锁84d + 各种锁仓配置
"""
import sys, os, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_vol_scaling)

NO_GOLD = {"510050":"SH50","159902":"ZZSM100","159915":"CYB",
           "510300":"HS300","159949":"CYB50","512100":"ZZ1000"}

raw, panel = build_panel(NO_GOLD, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

def run(M=1200, buy=0.7, sell=-1.0, rb=42, lock=0, no_neg=True):
    sig_raw, _, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0:
            eff = 1.0
        if eff == 0:
            hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None:
            lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= rb:
            scs = {}
            for c in NO_GOLD:
                if dt in mom[c].index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x:-x[1])
            sel = [c for c,v in rk if v>0] if no_neg else [c for c,v in rk]
            hold = sel[:1] if sel else []; lr = dt
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
        nd = m.sum()
        if nd < 5: continue
        yr_eq = (1 + ret[m]).cumprod()
        annual[yr] = round((yr_eq.iloc[-1] ** (252/nd) - 1) * 100, 1)
    cagr = eq.iloc[-1] ** (252/len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    pr = (pos.sum(axis=1) > 0).mean() * 100
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1),
            "W%": round(wr,1), "Pos%": round(pr,1), "Annual": annual}

print("="*80)
print("  剔除黄金，锁84d表现")
print("="*80)

base = run(1200, 0.7, -1.0, 42, 0)
print(f"\n  基线(无金): CAGR={base['CAGR']}%  Sharpe={base['Sharpe']}  MDD={base['MDD']}%  仓位={base['Pos%']}%")
if base['Annual']:
    print("  年: ", "  ".join(f"{yr}:{v:>5.1f}%" for yr,v in sorted(base['Annual'].items())))

print(f"\n── [无金+锁仓] 不同锁仓天数 ──")
for lock in [42, 63, 84]:
    r = run(1200, 0.7, -1.0, 63, lock)
    if r:
        print(f"\n  锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")
        print("  年: ", "  ".join(f"{yr}:{v:>5.1f}%" for yr,v in sorted(r['Annual'].items())))

# 对比：带金 vs 无金 锁84d
print(f"\n── [对比] 锁84d 带金 vs 无金 ──")
r_gold = None  # 之前的结果手动对比
r_nogold_84 = run(1200, 0.7, -1.0, 63, 84)
if r_nogold_84:
    print(f"  无金锁84d: CAGR={r_nogold_84['CAGR']}%  Sharpe={r_nogold_84['Sharpe']}  MDD={r_nogold_84['MDD']}%")
    print(f"  参考: 带金锁84d之前是28.3%/0.56/-21.1%")

# ── 不过滤负值 ──
print(f"\n── [无金+不过滤负+锁] ──")
for lock in [42, 63, 84]:
    r = run(1200, 0.7, -1.0, 63, lock, no_neg=False)
    if r:
        print(f"\n  无金不过滤+锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
        print("  年: ", "  ".join(f"{yr}:{v:>5.1f}%" for yr,v in sorted(r['Annual'].items())))

print(f"\n{'='*80}")
