"""
参数调整：低RSRS阈值 + 短动量窗口
标的池固定10只不变
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}
raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

# Pre-compute momentum at multiple windows
mom_cache = {}
for code, df in raw.items():
    cdf = df.set_index("date")["close"]
    mc = {}
    for w in [21, 42, 63, 84]:
        s = cdf.pct_change(w)
        mc[w] = s[s.index.isin(panel.index)]
    mom_cache[code] = mc

def run(M=900, buy=0.7, sell=-1.0, rb=63, lock=42, mom_w=63, no_neg=True):
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
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
            scs = {}
            for c in POOL:
                if dt in mom_cache[c][mom_w].index:
                    v = float(mom_cache[c][mom_w].loc[dt])
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
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        nd = m.sum()
        if nd < 5: continue
        annual[yr] = round((((1+ret[m]).cumprod())[-1]**(252/nd)-1)*100, 1)
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    pr = round((pos.sum(axis=1)>0).mean()*100, 1)
    vol = round(np.sqrt(252)*ret.std()*100, 1)
    wr = round((ret>0).sum()/len(ret)*100, 1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"Vol":vol,"Pos%":pr,"W%":wr,
            "Annual":annual,"M":M,"buy":buy,"sell":sell,"RB":rb,"Lock":lock,"MomW":mom_w,"NoNeg":no_neg}

SEP = "="*95
results = []

# ═══ Phase 1: 基准 (当前最优) ═══
print(SEP)
print("  阶段1: 基准结果 (当前最优参数)")
print(SEP)
r = run(M=900, buy=0.7, sell=-1.0, rb=63, lock=42, mom_w=63)
if r:
    results.append(("基准(M=900 buy=0.7 mom=63,锁42)", r))
    print(f"  CAGR={r['CAGR']}%  Sharpe={r['Sharpe']}  MDD={r['MDD']}%  Calmar={r['Calmar']}  Vol={r['Vol']}%  仓位={r['Pos%']}%")

# ═══ Phase 2: 改买入阈值 (保留63d动量) ═══
print(f"\n{SEP}")
print("  阶段2: 降低RSRS买入阈值 (动量63d)")
print(SEP)
for buy in [0.3, 0.5, 1.0]:
    r = run(M=900, buy=buy, sell=-1.0, rb=63, lock=42, mom_w=63)
    if r:
        lbl = f"buy={buy} mom=63"
        results.append((lbl, r))
        chg = round(r['CAGR'] - results[0][1]['CAGR'], 1)
        print(f"  buy={buy:.1f}: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ Phase 3: 改短动量窗口 ═══
print(f"\n{SEP}")
print("  阶段3: 缩短动量窗口 (buy=0.7)")
print(SEP)
for mw in [21, 42]:
    r = run(M=900, buy=0.7, sell=-1.0, rb=63, lock=42, mom_w=mw)
    if r:
        lbl = f"buy=0.7 mom={mw}"
        results.append((lbl, r))
        chg = round(r['CAGR'] - results[0][1]['CAGR'], 1)
        print(f"  mom={mw:>2}d: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ Phase 4: 低阈值 + 短动量 ══ 
print(f"\n{SEP}")
print("  阶段4: 低买入阈值 + 短动量窗口")
print(SEP)
for buy in [0.3, 0.5]:
    for mw in [21, 42]:
        r = run(M=900, buy=buy, sell=-1.0, rb=63, lock=42, mom_w=mw)
        if r:
            lbl = f"buy={buy} mom={mw}"
            results.append((lbl, r))
            chg = round(r['CAGR'] - results[0][1]['CAGR'], 1)
            print(f"  buy={buy:.1f} mom={mw:>2}d: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ Phase 5: 无锁仓 + 低阈值 + 短动量 ══
print(f"\n{SEP}")
print("  阶段5: 无锁仓 + 低阈值 + 短动量")
print(SEP)
for buy in [0.3, 0.5]:
    for mw in [21, 42]:
        r = run(M=900, buy=buy, sell=-1.0, rb=63, lock=0, mom_w=mw)
        if r:
            lbl = f"buy={buy} mom={mw} nolock"
            results.append((lbl, r))
            chg = round(r['CAGR'] - results[0][1]['CAGR'], 1)
            print(f"  buy={buy:.1f} mom={mw:>2}d 无锁: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ Phase 6: 全低阈值 + RB=42 + 短动量 ══
print(f"\n{SEP}")
print("  阶段6: RB=42 + 低阈值 + 短动量")
print(SEP)
for buy in [0.3, 0.5]:
    for mw in [21, 42]:
        r = run(M=900, buy=buy, sell=-1.0, rb=42, lock=42, mom_w=mw)
        if r:
            lbl = f"buy={buy} mom={mw} rb=42"
            results.append((lbl, r))
            chg = round(r['CAGR'] - results[0][1]['CAGR'], 1)
            print(f"  buy={buy:.1f} mom={mw:>2}d RB=42: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ Summary ═══
print(f"\n{SEP}")
print("  Summary (按Calmar排序)")
print(SEP)
results.sort(key=lambda x: -x[1]['Calmar'])
print(f"{'名称':<30} {'CAGR%':>6} {'Sharpe':>7} {'MDD%':>7} {'Calmar':>7} {'Vol%':>6} {'仓位%':>6}")
print("-"*80)
for name, r in results[:15]:
    print(f"{name:<30} {r['CAGR']:>5.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>6.1f}% {r['Calmar']:>6.2f} {r['Vol']:>5.1f}% {r['Pos%']:>5.0f}%")

# ═══ Top 3 分年 ═══
print(f"\n{SEP}")
print("  Top 3 分年明细")
print(SEP)
for name, r in results[:3]:
    print(f"\n  {name}")
    print(f"  全期: CAGR={r['CAGR']}%  Sharpe={r['Sharpe']}  MDD={r['MDD']}%  Calmar={r['Calmar']}")
    if r['Annual']:
        ann_str = "  ".join(f"{yr}:{v:>5.1f}%" for yr,v in sorted(r['Annual'].items()))
        print(f"  年: {ann_str}")

# Save
save_data = {name: {k:v for k,v in r.items() if k != 'Annual'} for name, r in results}
save_data.update({name: {k:v for k,v in r.items() if k in ['CAGR','Sharpe','MDD','Calmar','Vol','Pos%','buy','MomW']} for name, r in results})
with open("D:\\QClaw_Trading\\RSRS\\param_fix_pool.json","w",encoding="utf-8") as f:
    json.dump({name: {k:r[k] for k in ['CAGR','Sharpe','MDD','Calmar','Vol','Pos%','buy','MomW','RB','Lock']} for name,r in results}, 
              f, ensure_ascii=False, indent=2)
print(f"\n  已保存")
