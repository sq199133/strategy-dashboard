"""
深度优化：动量公式 + RSRS强度 + 权重方案
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

def custom_momentum(data, panel, lookbacks=(50,63,75)):
    """标准C63动量，支持自定义窗口"""
    ps = set(panel.index)
    mom = {}
    for code, df in data.items():
        dfi = df.set_index('date')
        d = {}
        for lb in lookbacks:
            d[f'ret_{lb}'] = dfi['close'].pct_change(lb)
        mdf = pd.DataFrame(d)
        mom[code] = mdf[mdf.index.isin(ps)]
    return mom

def custom_c63(mom_df, date, lookbacks=(50,63,75)):
    """C63得分，可自定义窗口"""
    r = mom_df.loc[date]
    vals = [r.get(f'ret_{lb}', np.nan) for lb in lookbacks]
    valid = [v for v in vals if not pd.isna(v)]
    return sum(valid) / len(valid) if valid else None

def momentum_v2(mom_data, date, method="c63", lookbacks=(50,63,75)):
    """
    method: 'c63' = 平均收益, 'slope' = 回归斜率, 'zscore' = 池内排名z分
    """
    scores = {}
    for code, mdf in mom_data.items():
        if date not in mdf.index:
            continue
        r = mdf.loc[date]
        if method.startswith("c63"):
            vals = [r.get(f'ret_{lb}', np.nan) for lb in lookbacks]
            vals = [v for v in vals if not pd.isna(v)]
            if vals:
                scores[code] = sum(vals) / len(vals)
        elif method.startswith("slope"):
            # 用最终回看期的收益替代（slope需要历史序列，先简化）
            vals = [r.get(f'ret_{lb}', np.nan) for lb in lookbacks]
            vals = [v for v in vals if not pd.isna(v)]
            if vals:
                scores[code] = sum(vals) / len(vals)
        elif method.startswith("zscore"):
            vals = [r.get(f'ret_{lb}', np.nan) for lb in lookbacks]
            vals = [v for v in vals if not pd.isna(v)]
            if vals:
                scores[code] = sum(vals) / len(vals)
    
    if method == "zscore" and scores:
        sv = np.array(list(scores.values()))
        if sv.std() > 1e-10:
            z = (sv - sv.mean()) / sv.std()
            for i, code in enumerate(scores):
                scores[code] = z[i]
    
    return scores

def run_custom_strategy(data, panel, sig, sig_dates, mom_data, rb, top, vol_scaling, 
                        score_method="c63", lookbacks=(50,63,75)):
    """
    替代run_strategy，支持自定义动量方法
    """
    sig_series = pd.Series(sig, index=pd.to_datetime(sig_dates))
    sig_on = sig_series.values.astype(float)
    
    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []  # 当前持仓列表
    last_rebal = None
    
    for i, date in enumerate(panel.index):
        dt = date
        
        # RSRS信号
        if dt in sig_series.index:
            if sig_series.loc[dt] == 0:
                holding = []
                continue
        
        # 调仓日判断
        is_rebal = (last_rebal is None) or ((dt - last_rebal).days >= rb)
        
        if is_rebal and sig_series.loc[dt] == 1:
            # 计算所有ETF的动量得分
            scores = momentum_v2(mom_data, dt, score_method, lookbacks)
            if not scores:
                holding = []
                continue
            
            # 选出top
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            if top > 0 and ranked[0][1] <= 0:
                holding = []
                continue
            
            selected = [c for c, s in ranked if s > 0][:top]
            
            if selected:
                holding = selected
                last_rebal = dt
        
        # 持仓权重
        if holding:
            w = 1.0 / len(holding)
            if dt in vol_scaling.index:
                w *= float(vol_scaling.loc[dt])
            for c in holding:
                if c in pos_df.columns:
                    pos_df.loc[dt, c] = w
    
    return pos_df

def evaluate(pool, N=18, M=1200, buy=0.7, sell=-1.0, top=1, rb=42, vw=70, tv=0.16,
             score_method="c63", lookbacks=(50,63,75)):
    try:
        data, panel = build_panel(pool, min_rows=200)
    except:
        return None
    df = load_etf("510300")
    sig, zs, bt = compute_rsrs(df, N, M, buy, sell)
    sd = df["date"].values
    
    mom = custom_momentum(data, panel, lookbacks)
    sc = compute_vol_scaling(df, panel.index, vw, tv)
    pos = run_custom_strategy(data, panel, sig, sd, mom, rb, top, sc, score_method, lookbacks)
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20:
        return None
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1), "W%": round(wr,1),
            "Method": score_method, "LBs": str(lookbacks), "Top": top, "RB": rb, "Days": len(ret)}

print("=" * 72)
print("  宽基池(CORE7) 深度动量优化")
print("=" * 72)

b = evaluate(CORE, 18, 1200, 0.7, -1.0, 1, 42, 70, 0.16)
print(f"\n  基线(原始C63): CAGR={b['CAGR']}%  Sharpe={b['Sharpe']}  MDD={b['MDD']}%")

# ── 方案A: 不同动量窗口 ──
print(f"\n\n── [A] 动量窗口扫描 ──")
for lbs in [(21,42,63), (42,63,84), (63,84,126), (84,126,168), (126,189,252)]:
    r = evaluate(CORE, 18, 1200, 0.7, -1.0, 1, 42, 70, 0.16, "c63", lbs)
    if r:
        print(f"  {str(lbs):<20}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 方案B: 池内z-score排名动量 ──
print(f"\n\n── [B] 池内z-score归一化 ──")
for lbs in [(50,63,75), (63,84,126), (126,189,252)]:
    r = evaluate(CORE, 18, 1200, 0.7, -1.0, 1, 42, 70, 0.16, "zscore", lbs)
    if r:
        print(f"  zscore {str(lbs):<20}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 方案C: 不同M值（都用最佳窗口） ──
print(f"\n\n── [C] 最佳窗口+M值组合 ──")
for M in [900, 1200, 1500]:
    for lbs in [(63,84,126), (84,126,168)]:
        r = evaluate(CORE, 18, M, 0.7, -1.0, 1, 42, 70, 0.16, "c63", lbs)
        if r:
            print(f"  M={M:>4} {str(lbs):<20}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 方案D: 波动率参数（最佳窗口） ──
print(f"\n\n── [D] 波动率 + 最佳窗口 ──")
for tv in [0.12, 0.16, 0.20, 0.25]:
    r = evaluate(CORE, 18, 1200, 0.7, -1.0, 1, 42, 70, tv, "c63", (63,84,126))
    if r:
        print(f"  TV={tv:.2f} CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 方案E: 买入阈值调优 ──
print(f"\n\n── [E] 阈值调优 ──")
for buy, sell in [(0.7,-1.0), (0.7,-1.5), (0.5,-1.0), (1.0,-1.0), (0.7,-0.5)]:
    r = evaluate(CORE, 18, 1200, buy, sell, 1, 42, 70, 0.16, "c63", (63,84,126))
    if r:
        print(f"  buy={buy:>3.1f} sell={sell:>+4.1f}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 方案F: 调仓频率 ──
print(f"\n\n── [F] 调仓频率 ──")
for rb in [21, 42, 63, 84]:
    r = evaluate(CORE, 18, 1200, 0.7, -1.0, 1, rb, 70, 0.16, "c63", (63,84,126))
    if r:
        print(f"  RB={rb:>2}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 方案G: 全部最佳合并 ──
print(f"\n\n── [G] 最佳组合验证 ──")
for M in [1200, 1500]:
    r = evaluate(CORE, 18, M, 0.7, -1.0, 1, 42, 70, 0.16, "c63", (84,126,168))
    if r:
        print(f"  M={M} LB=(84,126,168) Top1 RB=42:  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

print(f"\n{'='*72}")
print(f"  目标: 20%+  |  当前最优: ...")
print(f"{'='*72}")
