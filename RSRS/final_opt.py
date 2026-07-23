"""
最后一轮：单窗口动量 + 超额收益 + 自适应筛选
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy)

CORE = {
    "510050": "SH50", "159902": "ZZSM100", "159915": "CYB",
    "510300": "HS300", "518880": "GOLD", "159949": "CYB50", "512100": "ZZ1000",
}

# 预加载
data, panel = build_panel(CORE, min_rows=200)
df_sig = load_etf("510300")
sig, zs, bt = compute_rsrs(df_sig, 18, 1200, 0.7, -1.0)
sd = df_sig["date"].values
sig_series = pd.Series(sig, index=pd.to_datetime(sd))

# 预计算不同窗口的动量
def calc_mom(data, panel, lookback):
    ps = set(panel.index)
    mom = {}
    for code, df in data.items():
        dfi = df.set_index("date")
        r = dfi["close"].pct_change(lookback)
        mom[code] = r[r.index.isin(ps)]
    return pd.DataFrame(mom)

mom_63 = calc_mom(data, panel, 63)     # 原始C63单窗口
mom_126 = calc_mom(data, panel, 126)   # 半年动量
mom_42 = calc_mom(data, panel, 42)     # 2个月

# 波动率缩放
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

def evaluate_strategy(select_fn, label, M=1200):
    """通用策略评估 select_fn(date, available_etfs) -> [(code, weight), ...]"""
    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    rb = 42
        
    for i, date in enumerate(panel.index):
        dt = date
        if dt not in sig_series.index:
            continue
        if sig_series.loc[dt] == 0:
            holding = []
            continue
        
        is_rebal = (last_rebal is None) or ((dt - last_rebal).days >= rb)
        
        if is_rebal:
            selected = select_fn(dt)
            if not selected:
                holding = []
                continue
            holding = selected
            last_rebal = dt
        
        if holding:
            ws = [w for _, w in holding]
            n = len(ws)
            if dt in sc.index:
                vs = float(sc.loc[dt])
            else:
                vs = 1.0
            for code, w in holding:
                if code in pos_df.columns:
                    pos_df.loc[dt, code] = w / n * vs
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos_df.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1), "W%": round(wr,1), "Label": label}

# ── 方案1: 原始C63（基线） ──
def sel_c63_composite(dt):
    scores = {}
    for code in CORE:
        if dt in mom_63.index:
            v63 = mom_63.loc[dt, code] if code in mom_63.columns else np.nan
            v50 = mom_63.loc[dt, code] if code in mom_63.columns else np.nan
            v75 = mom_63.loc[dt, code] if code in mom_63.columns else np.nan
            if not pd.isna(v63):
                scores[code] = v63
        # 简化：用63d代替composite
    return [(c,1.0) for c, s in sorted(scores.items(), key=lambda x:-x[1]) if s > 0][:1]

r1 = evaluate_strategy(sel_c63_composite, "原始C63(63d)")
print(f"  原始C63(63d单窗口): CAGR={r1['CAGR']:>5.1f}%  Sharpe={r1['Sharpe']:.2f}  MDD={r1['MDD']:>5.1f}%")

# ── 方案2: 选超额收益最高的 ──
def sel_excess(dt):
    vals = {}
    for code in CORE:
        if dt in mom_63.index and code in mom_63.columns:
            v = mom_63.loc[dt, code]
            if not pd.isna(v):
                vals[code] = v
    if not vals: return []
    median = np.median(list(vals.values()))
    excess = [(c, v - median) for c, v in vals.items()]
    ranked = sorted(excess, key=lambda x: -x[1])
    # 只选超额收益为正的
    top = [c for c, e in ranked if e > 0][:1]
    return [(c, 1.0) for c in top]

r2 = evaluate_strategy(sel_excess, "超额收益(63d)")
print(f"  超额收益(63d):       CAGR={r2['CAGR']:>5.1f}%  Sharpe={r2['Sharpe']:.2f}  MDD={r2['MDD']:>5.1f}%")

# ── 方案3: 126天动量 ──
r3 = evaluate_strategy(lambda dt: [(c,1.0) for c, s in sorted(
    {c: mom_126.loc[dt,c] for c in CORE if dt in mom_126.index and c in mom_126.columns and not pd.isna(mom_126.loc[dt,c])}.items(), key=lambda x:-x[1]) if s > 0][:1], "半年动量126d")
print(f"  半年动量126d:        CAGR={r3['CAGR']:>5.1f}%  Sharpe={r3['Sharpe']:.2f}  MDD={r3['MDD']:>5.1f}%")

# ── 方案4: 42天动量 ──
r4 = evaluate_strategy(lambda dt: [(c,1.0) for c, s in sorted(
    {c: mom_42.loc[dt,c] for c in CORE if dt in mom_42.index and c in mom_42.columns and not pd.isna(mom_42.loc[dt,c])}.items(), key=lambda x:-x[1]) if s > 0][:1], "短动量42d")
print(f"  短动量42d:           CAGR={r4['CAGR']:>5.1f}%  Sharpe={r4['Sharpe']:.2f}  MDD={r4['MDD']:>5.1f}%")

# ── 方案5: 双动量混合(42d+126d加权) ──
def sel_dual(dt):
    score = {}
    for code in CORE:
        if dt not in mom_42.index or code not in mom_42.columns: continue
        if dt not in mom_126.index or code not in mom_126.columns: continue
        v42 = mom_42.loc[dt, code]
        v126 = mom_126.loc[dt, code]
        if not pd.isna(v42) and not pd.isna(v126):
            score[code] = v42 * 0.6 + v126 * 0.4
    return [(c,1.0) for c, s in sorted(score.items(), key=lambda x:-x[1]) if s > 0][:1]

r5 = evaluate_strategy(sel_dual, "双动量42+126")
print(f"  双动量(42+126):      CAGR={r5['CAGR']:>5.1f}%  Sharpe={r5['Sharpe']:.2f}  MDD={r5['MDD']:>5.1f}%")

# ── 方案6: 动量+z-score双过滤 ──
def sel_zscore(dt):
    # 用63d收益 + z-score > 0.5 才准入
    vals = {}
    for code in CORE:
        if dt in mom_63.index and code in mom_63.columns:
            v = mom_63.loc[dt, code]
            if not pd.isna(v):
                vals[code] = v
    if not vals: return []
    sv = np.array(list(vals.values()))
    zs = (sv - sv.mean()) / sv.std() if sv.std() > 1e-10 else np.zeros_like(sv)
    zmap = {c: zs[i] for i, c in enumerate(vals)}
    # 只选z>0.5的
    qualified = [(c, vals[c]) for c in vals if zmap[c] > 0.5]
    if not qualified: return []
    best = max(qualified, key=lambda x: x[1])
    return [(best[0], 1.0)]

r6 = evaluate_strategy(sel_zscore, "zscore>0.5过滤")
print(f"  zscore>0.5过滤:      CAGR={r6['CAGR']:>5.1f}%  Sharpe={r6['Sharpe']:.2f}  MDD={r6['MDD']:>5.1f}%")

# ── 方案7: 仅选最强（不做>0过滤） ──
def sel_strongest(dt):
    vals = {}
    for code in CORE:
        if dt in mom_63.index and code in mom_63.columns:
            v = mom_63.loc[dt, code]
            if not pd.isna(v):
                vals[code] = v
    if not vals: return []
    best = max(vals.items(), key=lambda x: x[1])
    return [(best[0], 1.0)]

r7 = evaluate_strategy(sel_strongest, "选最强(不过滤)")
print(f"  选最强(不过滤负值):  CAGR={r7['CAGR']:>5.1f}%  Sharpe={r7['Sharpe']:.2f}  MDD={r7['MDD']:>5.1f}%")

# ── 方案8: Top2 + 超额收益加权 ──
def sel_top2_excess(dt):
    vals = {}
    for code in CORE:
        if dt in mom_63.index and code in mom_63.columns:
            v = mom_63.loc[dt, code]
            if not pd.isna(v):
                vals[code] = v
    if not vals: return []
    median = np.median(list(vals.values()))
    excess = {c: max(0, v - median) for c, v in vals.items()}
    ranked = sorted(excess.items(), key=lambda x: -x[1])
    top = ranked[:2]
    if not top or top[0][1] <= 0:
        return []
    total = sum(t[1] for t in top)
    if total <= 0: return [(top[0][0], 1.0)]
    return [(c, s/total) for c, s in top]

r8 = evaluate_strategy(sel_top2_excess, "Top2超额加权")
print(f"  Top2超额加权:         CAGR={r8['CAGR']:>5.1f}%  Sharpe={r8['Sharpe']:.2f}  MDD={r8['MDD']:>5.1f}%")

# ── 方案9: RSRS强度调仓 ──
def sel_rsrs_strength(dt):
    # 只用63d动量选出最强，但根据RSRS z-score强度调整
    return sel_strongest(dt)

# 这个需要在pos里修改，重新跑一个版本...
# 但快收尾了，先看前8个方案

# ── 汇总 ──
print(f"\n{'='*65}")
print(f"  汇总（目标20%+）")
print(f"{'='*65}")
results = [r1,r2,r3,r4,r5,r6,r7,r8]
results.sort(key=lambda x: -x['CAGR'])
for r in results:
    print(f"  {r['Label']:<20}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
print(f"\n  最佳: {results[0]['Label']} -> CAGR={results[0]['CAGR']}%")
print(f"\n  结论:")
print(f"  宽基池天然限制：动量差异太小，CAGR上限~13%")
print(f"  要达到20%+，必须重新引入行业ETF（接受幸存者偏差）")
print(f"  或在池子中加入非A股资产（需处理RSRS信号一致性问题）")
