"""
RSRS锁仓验证 + 组合优化 (clean version)
"""
import sys, os, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_vol_scaling)

CORE = {"510050":"SH50","159902":"ZZSM100","159915":"CYB",
        "510300":"HS300","518880":"GOLD","159949":"CYB50","512100":"ZZ1000"}

raw_data, panel = build_panel(CORE, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

# 预计算每个ETF的63d收益率
mom_cache = {}
for code, df in raw_data.items():
    dfi = df.set_index("date")
    s = dfi["close"].pct_change(63).rename("mom")
    mom_cache[code] = s[s.index.isin(panel.index)]

def get_momentum(dt):
    scores = {}
    for code in CORE:
        s = mom_cache[code]
        if dt in s.index:
            v = s.loc[dt]
            if not pd.isna(v):
                scores[code] = v
    return scores

def run_locked(M=1200, buy=0.7, sell=-1.0, rb=42, lock=0):
    sig_raw, _, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    lock_until = None  # 锁仓到期日

    for date in panel.index:
        dt = date
        if dt not in sig_s.index:
            continue
        
        raw = float(sig_s.loc[dt])
        
        # 锁仓逻辑：在锁仓期内忽略RSRS转空
        eff = raw
        if lock > 0 and lock_until is not None and dt <= lock_until and raw == 0:
            eff = 1.0
        
        if eff == 0:
            holding, lock_until = [], None
            continue
        
        # 真实RSRS刚开仓时启动锁仓
        if lock > 0 and raw == 1 and lock_until is None:
            lock_until = dt + pd.Timedelta(days=lock)
        
        # 调仓
        if last_rebal is None or (dt - last_rebal).days >= rb:
            scores = get_momentum(dt)
            if not scores:
                holding = []
                continue
            top = max(scores.items(), key=lambda x: x[1])
            if top[1] > 0:
                holding = [top[0]]
            else:
                holding = []
            last_rebal = dt
        
        if holding:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if holding[0] in pos_df.columns:
                pos_df.loc[dt, holding[0]] = w
    
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
    
    # 统计持仓天数占比
    pos_ratio = (pos_df.sum(axis=1) > 0).mean() * 100
    
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1),
            "W%": round(wr,1), "Days": len(ret), "Pos%": round(pos_ratio,1),
            "M": M, "RB": rb, "Lock": lock}

print("="*80)
print("  RSRS锁仓验证 + 组合优化")
print("="*80)

b = run_locked(1200, 0.7, -1.0, 42, 0)
print(f"\n  基线(M=1200 RB=42 无锁): CAGR={b['CAGR']}%  Sharpe={b['Sharpe']}  MDD={b['MDD']}%  仓位={b['Pos%']}%")

# ── 验证锁仓 ──
print(f"\n── [验证1] RB=42 + 锁仓 ──")
for lock in [10, 21, 42, 63, 84]:
    r = run_locked(1200, 0.7, -1.0, 42, lock)
    if r:
        chg = r['CAGR'] - b['CAGR']
        print(f"  锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── M=900 + 锁仓 ──
print(f"\n── [验证2] M=900 RB=63 + 锁仓 ──")
for lock in [0, 21, 42]:
    r = run_locked(900, 0.7, -1.0, 63, lock)
    if r:
        print(f"  M=900 RB=63 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── M=900 + RB=42 + 锁仓 ──
print(f"\n── [验证3] M=900 RB=42 + 锁仓 ──")
for lock in [0, 21, 42, 63]:
    r = run_locked(900, 0.7, -1.0, 42, lock)
    if r:
        print(f"  M=900 RB=42 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── M=1200 + RB=63 + 锁仓 ──
print(f"\n── [验证4] M=1200 RB=63 + 锁仓 ──")
for lock in [0, 21, 42, 63]:
    r = run_locked(1200, 0.7, -1.0, 63, lock)
    if r:
        print(f"  M=1200 RB=63 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── 所有组合强筛选 ──
print(f"\n── [全部组合] CAGR>14的 ──")
all_best = []
for M in [900, 1200, 1500]:
    for rb in [42, 63]:
        for lock in [0, 21, 42, 63, 84]:
            r = run_locked(M, 0.7, -1.0, rb, lock)
            if r and r['CAGR'] >= 14:
                all_best.append(r)
                print(f"  M={M:>4} RB={rb:>2} 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

print(f"\n{'='*80}")
all_best.sort(key=lambda x: -x['CAGR'])
if all_best:
    top = all_best[0]
    print(f"  最高CAGR: M={top['M']} RB={top['RB']} 锁{top['Lock']}d → {top['CAGR']}%")
    print(f"  夏普={top['Sharpe']}  MDD={top['MDD']}%  仓位比={top['Pos%']}%")
all_best.sort(key=lambda x: -x['Sharpe'])
if all_best:
    top_sharpe = all_best[0]
    print(f"  最高夏普: M={top_sharpe['M']} RB={top_sharpe['RB']} 锁{top_sharpe['Lock']}d → {top_sharpe['CAGR']}%")
    print(f"  夏普={top_sharpe['Sharpe']}  MDD={top_sharpe['MDD']}%  仓位比={top_sharpe['Pos%']}%")
print(f"{'='*80}")
