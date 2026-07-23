"""
最后几枪：高门槛 + 长锁仓 + 分年明细
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

mom_cache = {}
for code, df in raw_data.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom_cache[code] = s[s.index.isin(panel.index)]

def run_locked(M=1200, buy=0.7, sell=-1.0, rb=42, lock=0, top_n=1, 
               must_pos_mom=True, max_pos=None):
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    zs_s = pd.Series(zs_raw, index=pd.to_datetime(df_sig["date"].values))
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    lock_until = None

    for date in panel.index:
        dt = date
        if dt not in sig_s.index: continue
        raw = float(sig_s.loc[dt])
        
        eff = raw
        if lock > 0 and lock_until is not None and dt <= lock_until and raw == 0:
            eff = 1.0
        
        if eff == 0:
            holding, lock_until = [], None
            continue
        
        if lock > 0 and raw == 1 and lock_until is None:
            # RSRS强度越大，锁仓时间越长
            z = float(zs_s.loc[dt])
            if max_pos is not None and z < max_pos:
                lock_until = dt + pd.Timedelta(days=lock)
            else:
                lock_until = dt + pd.Timedelta(days=lock)
        
        if last_rebal is None or (dt - last_rebal).days >= rb:
            scores = {}
            for code in CORE:
                s = mom_cache[code]
                if dt in s.index:
                    v = s.loc[dt]
                    if not pd.isna(v):
                        scores[code] = v
            if not scores:
                holding = []
                continue
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            
            # 动量过滤
            if must_pos_mom:
                pos = [c for c, v in ranked if v > 0]
            else:
                pos = [c for c, v in ranked]
            
            if top_n > 0 and pos:
                selected = pos[:top_n]
            else:
                selected = []
            
            if selected:
                holding = selected
            else:
                holding = []
            last_rebal = dt
        
        if holding:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            for c in holding:
                if c in pos_df.columns:
                    pos_df.loc[dt, c] = w / len(holding)
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos_df.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    
    # 分年
    years = sorted(set(d.year for d in ret.index))
    annual = {}
    for yr in years:
        mask = ret.index.year == yr
        nd = mask.sum()
        if nd < 5: continue
        yr_eq = (1 + ret[mask]).cumprod()
        annual[yr] = round((yr_eq.iloc[-1] ** (252 / nd) - 1) * 100, 1)
    
    cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    pos_ratio = (pos_df.sum(axis=1) > 0).mean() * 100
    
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1),
            "W%": round(wr,1), "Pos%": round(pos_ratio,1), "Annual": annual,
            "M": M, "RB": rb, "Lock": lock, "Top": top_n}

print("="*95)
print("  最终冲刺：高门槛 + 长锁仓")
print("="*95)

# ── buy=1.0 + 锁仓 ──
print(f"\n── [buy=1.0] 高门槛入场 ──")
for lock in [42, 63, 84]:
    r = run_locked(1200, 1.0, -1.0, 63, lock)
    if r:
        print(f"  buy=1.0 RB=63 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── Top2 + 锁仓 ──
print(f"\n── [Top2] 分散持有 ──")
for lock in [42, 63]:
    r = run_locked(1200, 0.7, -1.0, 63, lock, top_n=2)
    if r:
        print(f"  Top2 RB=63 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── 不过滤负值 + 长锁 ──
print(f"\n── [不过滤负值] 始终持有最强ETF ──")
for lock in [42, 63]:
    r = run_locked(1200, 0.7, -1.0, 63, lock, must_pos_mom=False)
    if r:
        print(f"  不过滤负 RB=63 锁{lock:>2}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  仓位={r['Pos%']:.0f}%")

# ── 最佳组合分年明细 ──
print(f"\n── [分年明细] 4个候选方案 ──")
candidates = [
    ("基   线", run_locked(1200, 0.7, -1.0, 42, 0)),
    ("A:稳 健", run_locked(1200, 0.7, -1.0, 63, 63)),
    ("B:激 进", run_locked(1200, 0.7, -1.0, 63, 84)),
    ("C:高迈+锁", run_locked(1200, 1.0, -1.0, 63, 84)),
    ("D:不过滤+锁", run_locked(1200, 0.7, -1.0, 63, 63, must_pos_mom=False)),
]

for name, r in candidates:
    if r:
        print(f"\n  {name}: CAGR={r['CAGR']}%  Sharpe={r['Sharpe']}  MDD={r['MDD']}%  仓位={r['Pos%']}%  Top1 锁定{r['Lock']}d")
        print(f"    年: ", end="")
        for yr in sorted(r['Annual'].keys()):
            print(f"{yr}:{r['Annual'][yr]:>5.1f}%", end="  ")
        print()

# ── 买+不卖（纯持有）对比 ──
print(f"\n── [纯买不卖] 只要RSRS开多就永远持有 ──")
r_till_sold = run_locked(1200, 0.7, -1.0, 63, 99999)  # lock极大=永不转空
if r_till_sold:
    print(f"  纯买不卖: CAGR={r_till_sold['CAGR']}%  Sharpe={r_till_sold['Sharpe']}  MDD={r_till_sold['MDD']}%  仓位={r_till_sold['Pos%']}%")
    print(f"    年: ", end="")
    for yr in sorted(r_till_sold['Annual'].keys()):
        print(f"{yr}:{r_till_sold['Annual'][yr]:>5.1f}%", end="  ")
    print()

print(f"\n{'='*95}")

# 保存结果
results_save = {"baseline": b['CAGR'] if (b:=run_locked(1200, 0.7, -1.0, 42, 0)) else 0}
for name, r in candidates:
    if r:
        results_save[name] = r['CAGR']
import json
with open("D:\\QClaw_Trading\\RSRS\\lock_results.json", "w") as f:
    json.dump(results_save, f, ensure_ascii=False, indent=2)
print(f"  结果已保存")
