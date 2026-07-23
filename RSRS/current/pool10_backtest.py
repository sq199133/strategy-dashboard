"""
新10只池子回测：锁仓优化
"""
import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

# Avoid GBK issues
sys.stdout.reconfigure(encoding='utf-8')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD",  #"162411":"OIL" 已剔除
}

print("="*80)
print("  新10只池子回测：基线与锁仓优化")
print("="*80)

raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

# Pre-compute 63d momentum
mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

def run(M=1200, buy=0.7, sell=-1.0, rb=42, lock=0, no_neg=True):
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
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
            for c in POOL:
                if dt in mom[c].index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
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
    
    # Annual breakdown
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
    calmar = round(cagr*100 / abs(mdd*100), 2) if mdd < 0 else 0
    
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1),
            "W%": round(wr,1), "Pos%": round(pr,1), "Calmar": calmar,
            "Annual": annual, "M": M, "RB": rb, "Lock": lock, "NoNeg": no_neg}

# ═══ 基线 ═══
print(f"\n── [基线] ──")
base = run(1200, 0.7, -1.0, 42, 0)
if base:
    print(f"  CAGR={base['CAGR']}%  Sharpe={base['Sharpe']}  MDD={base['MDD']}%  Calmar={base['Calmar']}  仓位={base['Pos%']}%")
    print("  年: ", "  ".join(f"{yr}:{v:>5.1f}%" for yr,v in sorted(base['Annual'].items())))

# ═══ 锁仓测试 ═══
print(f"\n── [锁仓测试] RB=42 ──")
for lock in [21, 42, 63, 84]:
    r = run(1200, 0.7, -1.0, 42, lock)
    if r:
        chg = round(r['CAGR'] - base['CAGR'], 1) if base else 0
        print(f"  锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

print(f"\n── [锁仓测试] RB=63 ──")
for lock in [0, 21, 42, 63, 84]:
    r = run(1200, 0.7, -1.0, 63, lock)
    if r:
        chg = round(r['CAGR'] - base['CAGR'], 1) if base else 0
        print(f"  RB=63 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ 不过滤负值 ═══
print(f"\n── [锁仓 + 不过滤负动量] ──")
for lock in [42, 63, 84]:
    r = run(1200, 0.7, -1.0, 63, lock, no_neg=False)
    if r:
        print(f"  不过滤 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}")

# ═══ M=900 ═══
print(f"\n── [M=900 RB=63 + 锁仓] ──")
for lock in [0, 42, 63, 84]:
    r = run(900, 0.7, -1.0, 63, lock)
    if r:
        print(f"  M=900 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}")

# ═══ 候选方案分年明细 ═══
candidates = [
    ("基线(Baseline)", run(1200, 0.7, -1.0, 42, 0)),
    ("锁63d",           run(1200, 0.7, -1.0, 42, 63)),
    ("RB=63 锁63d",     run(1200, 0.7, -1.0, 63, 63)),
    ("RB=63 锁84d",     run(1200, 0.7, -1.0, 63, 84)),
    ("不过滤+锁63d",    run(1200, 0.7, -1.0, 63, 63, no_neg=False)),
    ("不过滤+锁84d",    run(1200, 0.7, -1.0, 63, 84, no_neg=False)),
]

print(f"\n── [候选方案 分年明细] ──")
print(f"{'方案':<18} {'CAGR':>6} {'Sharpe':>7} {'MDD':>7} {'Calmar':>7} 年收益")
print("-"*100)
for name, r in candidates:
    if not r: continue
    ann = "  ".join(f"{yr}:{r['Annual'][yr]:>5.1f}%" for yr in sorted(r['Annual'].keys()) if yr in r['Annual'])
    print(f"{name:<18} {r['CAGR']:>5.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>6.1f}% {r['Calmar']:>6.2f}  {ann}")

# ═══ Save ═══
results_data = {}
for name, r in candidates:
    if r:
        results_data[name] = {
            "CAGR": r["CAGR"], "Sharpe": r["Sharpe"], "MDD": r["MDD"],
            "Calmar": r["Calmar"], "Pos%": r["Pos%"], "Annual": r["Annual"]
        }
with open("D:\\QClaw_Trading\\RSRS\\pool10_results.json","w",encoding="utf-8") as f:
    json.dump(results_data, f, ensure_ascii=False, indent=2)

print(f"\n{'='*80}")
print(f"  结果已保存")
