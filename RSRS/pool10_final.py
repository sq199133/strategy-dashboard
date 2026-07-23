"""
10只新池 - 最终对比 + 最佳方案分年明细
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD",
        "162411":"OIL"}
raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

def run(M, rb, lock, no_neg=True, buy=0.7, sell=-1.0):
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s, zs_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values)), pd.Series(zs_raw, index=pd.to_datetime(df_sig["date"].values))
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
                if dt in mom[c].index:
                    v = float(mom[c].loc[dt])
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
        annual[yr] = round((((1+ret[m]).cumprod()).iloc[-1]**(252/nd)-1)*100, 1)
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    pr = round((pos.sum(axis=1)>0).mean()*100, 1)
    vol = round(np.sqrt(252)*ret.std()*100, 1)
    wr = round((ret>0).sum()/len(ret)*100, 1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"Pos%":pr,"Vol":vol,"W%":wr,"Annual":annual}

# ═══ 候选方案对比 ═══
candidates = [
    ("基线",                     1200, 42, 0),
    ("每周调仓+锁21d",          1200, 21, 21),
    ("RB=63无锁",                1200, 63, 0),
    ("RB=63锁42d",              1200, 63, 42),
    ("M=900 RB=63无锁",          900, 63, 0),
    ("M=900 RB=63锁42d",        900, 63, 42),  # ⭐
    ("M=900 RB=63锁63d",        900, 63, 63),
    ("RB=63锁84d (备选高收益)",  1200, 63, 84),
]

print("="*90)
print("  10只新池 - 候选方案对比")
print("="*90)
print(f"{'方案':<24} {'CAGR%':>6} {'Sharpe':>7} {'MDD%':>7} {'Calmar':>7} {'Vol%':>6} {'仓位%':>6}")
print("-"*90)
for name, M, rb, lock in candidates:
    r = run(M, rb, lock)
    if r:
        print(f"{name:<24} {r['CAGR']:>5.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>6.1f}% {r['Calmar']:>6.2f} {r['Vol']:>5.1f}% {r['Pos%']:>5.0f}%")

# ═══ 最佳方案分年 ═══
print(f"\n{'='*90}")
print(f"  最佳方案分年 (M=900 RB=63 Lock=42)")
print(f"{'='*90}")
best = run(900, 63, 42)
if best:
    print(f"\n  全期: CAGR={best['CAGR']}%  Sharpe={best['Sharpe']}  MDD={best['MDD']}%  Calmar={best['Calmar']}  Vol={best['Vol']}% 仓位={best['Pos%']}% 胜率={best['W%']}%")
    print(f"\n  分年:")
    print(f"  {'年份':>6} {'收益':>8}{' ':<2} {'年份':>6} {'收益':>8}")
    ys = sorted(best['Annual'].keys())
    mid = len(ys)//2 + len(ys)%2
    for i in range(mid):
        y1, v1 = ys[i], best['Annual'][ys[i]]
        if i+mid < len(ys):
            y2, v2 = ys[i+mid], best['Annual'][ys[i+mid]]
            print(f"  {y1:>6} {v1:>7.1f}%{'':<5} {y2:>6} {v2:>7.1f}%")
        else:
            print(f"  {y1:>6} {v1:>7.1f}%")

# ═══ 基线 vs 最佳 分年对比 ═══
base = run(1200, 42, 0)
print(f"\n{'='*90}")
print(f"  基线 vs 最佳 (分年)")
print(f"{'='*90}")
print(f"  {'年份':>6} {'基线%':>8} {'最佳%':>8} {'差值%':>8}")
print(f"  {'-'*32}")
all_yrs = sorted(set(list(base['Annual'].keys()) + list(best['Annual'].keys())))
for yr in all_yrs:
    bv = base['Annual'].get(yr, 0)
    bst = best['Annual'].get(yr, 0)
    print(f"  {yr:>6} {bv:>7.1f}% {bst:>7.1f}% {(bst-bv):>+7.1f}%")
print(f"  {'-'*32}")
print(f"  全期: {base['CAGR']:>7.1f}% {best['CAGR']:>7.1f}% {(best['CAGR']-base['CAGR']):>+7.1f}%")

print(f"\n{'='*90}")
print(f"  最终参数配置")
print(f"{'='*90}")
print(f"  标的池: 10只 (5A股宽基+科创50+标普500+纳指+黄金+原油)")
print(f"  RSRS: N=18, M=900, buy=0.7, sell=-1.0")
print(f"  Momentum: 63d单窗口收益率")
print(f"  䐛仓: RB=63 (每63交易日换仓)")
print(f"  锁仓: Lock=42 (开多后锁定42天不转空)")
print(f"  䐛仓: Top1, 过滤负动量")
print(f"  䐛位缩放: VW=70, TV=0.16, 持仓=满仓*缩放")
print(f"{'='*90}")

# Save
json.dump({"candidates": {name: run(M,rb,lock) for name,M,rb,lock in candidates if run(M,rb,lock)}},
          open("D:\\QClaw_Trading\\RSRS\\pool10_final.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n  已保存: pool10_final.json")
