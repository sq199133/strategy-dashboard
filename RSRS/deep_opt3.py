"""
更激进的组合优化：z-score强度仓位 + 最佳动量
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

def momentum_v2(mom_data, date, lookbacks=(50,63,75)):
    """返回z-score归一化的动量（池内横行比较）"""
    scores = {}
    for code, mdf in mom_data.items():
        if date not in mdf.index: continue
        r = mdf.loc[date]
        vals = [r.get(f'ret_{lb}', np.nan) for lb in lookbacks]
        vals = [v for v in vals if not pd.isna(v)]
        if vals:
            scores[code] = sum(vals) / len(vals)
    if not scores: return {}
    sv = np.array(list(scores.values()))
    if sv.std() > 1e-10:
        z = (sv - sv.mean()) / sv.std()
        for i, code in enumerate(scores):
            scores[code] = z[i]
    else:
        for code in scores:
            scores[code] = 0.0
    return scores

def run_custom_strategy(data, panel, sig, sig_dates, mom_data, rb, top, vol_scaling,
                        lookbacks=(50,63,75), zscore_pos=False, buy_sell_scale=False,
                        pos_by_rank=False):
    """
    zscore_pos: 用z-score归一化动量代替原始C63
    buy_sell_scale: 根据RSRS z-score强度缩放仓位
    pos_by_rank: 按排名加权（不再是平均权重）
    """
    sig_series = pd.Series(sig, index=pd.to_datetime(sig_dates))
    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    
    # 预计算RSRS z-score用于仓位缩放
    # 从sig_dates重建z-score序列
    # 这里简单处理：如果buy_sell_scale=True, 用sig值+倍数

    for i, date in enumerate(panel.index):
        dt = date
        if dt not in sig_series.index:
            continue
        
        sig_val = float(sig_series.loc[dt])
        
        if sig_val == 0:
            holding = []
            continue
        
        # RSRS强度系数
        rsrs_strength = 1.0  # 默认满仓
        
        # 调仓日
        is_rebal = (last_rebal is None) or ((dt - last_rebal).days >= rb)
        
        if is_rebal:
            # 选动量最强的
            scores = momentum_v2(mom_data, dt, lookbacks)
            if not scores:
                holding = []
                continue
            
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            
            # 过滤：只选正动量
            pos_ranked = [c for c, s in ranked if s > 0]
            
            if top > 0 and not pos_ranked:
                holding = []
                continue
            
            selected = pos_ranked[:top]
            
            if selected:
                holding = selected
                last_rebal = dt
        
        # 确定权重
        if holding:
            n = len(holding)
            if pos_by_rank and n > 0:
                # 按动量得分比例加权
                scores_held = [momentum_v2(mom_data, dt, lookbacks).get(c, 0) for c in holding]
                total_s = sum(max(0, s) for s in scores_held)
                if total_s > 0:
                    weights = [max(0, s) / total_s for s in scores_held]
                else:
                    weights = [1.0/n] * n
            else:
                weights = [1.0/n] * n
            
            # 波动率缩放
            vs = 1.0
            if dt in vol_scaling.index:
                vs = float(vol_scaling.loc[dt])
            
            # z-score强度位
            if zscore_pos:
                # 只选z-score > 0.5的
                s_all = momentum_v2(mom_data, dt, lookbacks)
                final_holding = []
                final_weights = []
                for c, w in zip(holding, weights):
                    if c in s_all and s_all[c] > 0.5:
                        final_holding.append(c)
                        final_weights.append(w)
                if not final_holding:
                    holding = []
                    continue
                holding = final_holding
                weights = final_weights
                w_sum = sum(weights)
                weights = [w/w_sum for w in weights]
            
            for c, w in zip(holding, weights):
                if c in pos_df.columns:
                    pos_df.loc[dt, c] = w * vs
    
    return pos_df

def evaluate(pool, N=18, M=1200, buy=0.7, sell=-1.0, top=1, rb=42, vw=70, tv=0.16,
             lookbacks=(50,63,75), zscore_pos=False, pos_by_rank=False, label=""):
    try:
        data, panel = build_panel(pool, min_rows=200)
    except:
        return None
    df = load_etf("510300")
    sig, zs, bt = compute_rsrs(df, N, M, buy, sell)
    sd = df["date"].values
    mom = custom_momentum(data, panel, lookbacks)
    sc = compute_vol_scaling(df, panel.index, vw, tv)
    pos = run_custom_strategy(data, panel, sig, sd, mom, rb, top, sc, lookbacks, zscore_pos, pos_by_rank)
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1), "W%": round(wr,1), "Label": label, "Days": len(ret)}

print("=" * 75)
print("  宽基池 - 激进组合优化")
print("=" * 75)

baseline = evaluate(CORE, label="基线")
print(f"\n  基线: CAGR={baseline['CAGR']}%  Sharpe={baseline['Sharpe']}  MDD={baseline['MDD']}%")

# ── 1. 基线 + RB=63 ──
print(f"\n── [1] RB调优(基线动量) ──")
for rb in [21, 42, 63, 84]:
    r = evaluate(CORE, rb=rb, label=f"RB={rb}")
    print(f"  RB={rb:>2}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 2. z-score动量 + buy阈值 ──
print(f"\n── [2] z-score动量 + 阈值 ──")
for buy in [0.7, 1.0, 1.5]:
    for sell in [-1.0, -1.5]:
        r = evaluate(CORE, buy=buy, sell=sell, lookbacks=(50,63,75), zscore_pos=True,
                     label=f"zscore buy={buy} sell={sell}")
        if r:
            print(f"  zscore buy={buy:>3.1f} sell={sell:>+4.1f}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 3. buy=1.0 + RB调优 ──
print(f"\n── [3] buy=1.0 + RB ──")
for rb in [21, 42, 63]:
    r = evaluate(CORE, buy=1.0, sell=-1.0, rb=rb, label=f"buy=1 RB={rb}")
    print(f"  buy=1.0 RB={rb:>2}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 4. z-score + buy=1.0 + RB ──
print(f"\n── [4] z-score + buy=1.0 + RB ──")
for rb in [42, 63]:
    for M in [1200, 1500]:
        r = evaluate(CORE, M=M, buy=1.0, sell=-1.0, rb=rb, lookbacks=(50,63,75), zscore_pos=True,
                     label=f"zscore buy=1 M={M} RB={rb}")
        print(f"  zscore buy=1 M={M} RB={rb:>2}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 5. z-score + 强度过滤 ──
print(f"\n── [5] z-score强度过滤（不同阈值） ──")
# 通过修改c63_score的筛选，这里zscore_pos=True默认要求z>0.5
# 再试试z>0的直接选

# 6. 全量组合
print(f"\n── [6] 最佳组合验证 ──")
# 组合A: buy=1.0 + RB=63 + M=1200
r = evaluate(CORE, M=1200, buy=1.0, sell=-1.0, rb=63, label="OptA")
print(f"  OptA: buy=1 M=1200 RB=63:  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
# 组合B: buy=1.0 + RB=21 + M=1200
r = evaluate(CORE, M=1200, buy=1.0, sell=-1.0, rb=21, label="OptB")
print(f"  OptB: buy=1 M=1200 RB=21:  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
# 组合C: zscore + buy=1 + RB=63 + M=1500
r = evaluate(CORE, M=1500, buy=1.0, sell=-1.0, rb=63, lookbacks=(50,63,75), zscore_pos=True, label="OptC")
if r:
    print(f"  OptC: zscore buy=1 M=1500 RB=63:  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# 组合D: 原始C63 + buy=0.5
r = evaluate(CORE, M=1200, buy=0.5, sell=-1.0, rb=42, label="OptD")
print(f"  OptD: buy=0.5 M=1200 RB=42:  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# 组合E: 原始C63 + buy=0.5 + RB=63
r = evaluate(CORE, M=1200, buy=0.5, sell=-1.0, rb=63, label="OptE")
print(f"  OptE: buy=0.5 M=1200 RB=63:  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

print(f"\n{'='*75}")
print(f"  目标: 20% CAGR")
print(f"{'='*75}")
