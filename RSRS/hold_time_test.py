"""
持仓时间效应：更长持有期
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

# 预加载信号
data, panel = build_panel(CORE, min_rows=200)
df_sig = load_etf("510300")

# 预计算单窗口63d动量
def calc_mom(data, panel, lookback):
    ps = set(panel.index)
    mom = {}
    for code, df in data.items():
        dfi = df.set_index("date")
        r = dfi["close"].pct_change(lookback)
        mom[code] = r[r.index.isin(ps)]
    return pd.DataFrame(mom)

mom_63 = calc_mom(data, panel, 63)
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

def evaluate_rb(RB, M=1200, buy=0.7, sell=-1.0, label=""):
    sig, zs, bt = compute_rsrs(df_sig, 18, M, buy, sell)
    sd = df_sig["date"].values
    sig_series = pd.Series(sig, index=pd.to_datetime(sd))
    
    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    
    for i, date in enumerate(panel.index):
        dt = date
        if dt not in sig_series.index: continue
        if sig_series.loc[dt] == 0:
            holding = []
            continue
        
        is_rebal = (last_rebal is None) or ((dt - last_rebal).days >= RB)
        
        if is_rebal:
            scores = {}
            for code in CORE:
                if dt in mom_63.index and code in mom_63.columns:
                    v = mom_63.loc[dt, code]
                    if not pd.isna(v):
                        scores[code] = v
            if not scores:
                holding = []
                continue
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            # 不过滤负值（可能选得到，但可能浪费）
            best = ranked[0]
            if best[1] > 0:
                holding = [best[0]]
            else:
                holding = []
            last_rebal = dt
        
        if holding:
            if dt in sc.index:
                w = float(sc.loc[dt])
            else:
                w = 1.0
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
    
    # 年化换手率（年调仓次数）
    n_rebal = 0
    last_rb = None
    for dt in ret.index:
        if dt not in sig_series.index: continue
        if sig_series.loc[dt] == 1:
            if last_rb is None or (dt - last_rb).days >= RB:
                n_rebal += 1
                last_rb = dt
    annual_turnover = n_rebal / (len(ret) / 252)
    
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1), "W%": round(wr,1),
            "RB": RB, "M": M, "Label": label, "Turnover": round(annual_turnover,1), "Days": len(ret)}

print("=" * 75)
print("  持仓时间效应分析")
print("=" * 75)

# ── 核心实验：调仓间隔 ──
print(f"\n── [核心] 调仓间隔 (RB) ──")
results_rb = []
for rb in [21, 42, 63, 84, 126, 168, 252]:
    r = evaluate_rb(rb, 1200, 0.7, -1.0, label=f"RB={rb}")
    if r:
        results_rb.append(r)
        print(f"  RB={rb:>3} ({rb/21:.0f}周): CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  年换手={r['Turnover']:>4.1f}次")

# ── 不同M值 + RB ──
print(f"\n── [组合] M + RB ──")
for M in [900, 1200, 1500]:
    for rb in [63, 126, 252]:
        r = evaluate_rb(rb, M, 0.7, -1.0, label=f"M={M} RB={rb}")
        if r:
            print(f"  M={M:>4} RB={rb:>3}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── RSRS锁仓 ──
print(f"\n── [RSRS锁仓] 锁仓期间忽略RSRS转空 ──")
for lock_days in [10, 21, 42, 63]:
    sig_lock, _, _ = compute_rsrs(df_sig, 18, 1200, 0.7, -1.0)
    # 锁仓逻辑：进入做多后，至少lock_days天内不转空
    sig_lock_arr = sig_lock.copy()
    last_long_end = -999999
    for i in range(len(sig_lock)):
        if sig_lock_arr[i] == 1:
            if i - last_long_end <= lock_days:
                sig_lock_arr[i] = 1  # 保持在锁仓期
            else:
                pass  # 正常开仓
        else:
            pass
    
    # 改用run_strategy跑需要修改信号，不灵活。直接测简化版
    sd = df_sig["date"].values
    sig_series_lock = pd.Series(sig_lock_arr, index=pd.to_datetime(sd))
    
    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    rb = 42
    lock_until = None
    
    for i, date in enumerate(panel.index):
        dt = date
        if dt not in sig_series_lock.index: continue
        
        sig_val = float(sig_series_lock.loc[dt])
        
        # 锁仓逻辑
        if lock_until is not None and dt < lock_until:
            sig_val = 1.0  # 忽略RSRS转空
        
        if sig_val == 0:
            holding = []
            continue
        
        if lock_until is not None and dt >= lock_until:
            lock_until = None
        
        is_rebal = (last_rebal is None) or ((dt - last_rebal).days >= rb)
        
        if is_rebal:
            scores = {}
            for code in CORE:
                if dt in mom_63.index and code in mom_63.columns:
                    v = mom_63.loc[dt, code]
                    if not pd.isna(v):
                        scores[code] = v
            if not scores:
                holding = []
                continue
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            best = ranked[0]
            if best[1] > 0:
                holding = [best[0]]
                lock_until = dt + pd.Timedelta(days=lock_days)
            else:
                holding = []
            last_rebal = dt
        
        if holding:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if holding[0] in pos_df.columns:
                pos_df.loc[dt, holding[0]] = w
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos_df.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[1200])
    ret = ret[ret.index >= fs]
    if len(ret) >= 20:
        eq = (1 + ret).cumprod()
        cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
        sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
        mdd = ((eq - eq.cummax()) / eq.cummax()).min()
        print(f"  锁仓{lock_days:>3}d: CAGR={round(cagr*100,1):>5.1f}%  Sharpe={sp:.2f}  MDD={round(mdd*100,1):>5.1f}%")

# ── 最小持仓锁定 ──
print(f"\n── [最小持仓] 选到后最少拿X天不换 ──")
for min_hold in [21, 42, 63, 126]:
    sig, _, _ = compute_rsrs(df_sig, 18, 1200, 0.7, -1.0)
    sd = df_sig["date"].values
    sig_series2 = pd.Series(sig, index=pd.to_datetime(sd))

    pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    holding = []
    last_rebal = None
    last_buy_date = None
    rb = 42

    for i, date in enumerate(panel.index):
        dt = date
        if dt not in sig_series2.index: continue
        if sig_series2.loc[dt] == 0:
            holding = []
            continue

        # 未到最小持仓，不换
        if last_buy_date is not None and (dt - last_buy_date).days < min_hold:
            if holding:
                w = float(sc.loc[dt]) if dt in sc.index else 1.0
                if holding[0] in pos_df.columns:
                    pos_df.loc[dt, holding[0]] = w
            continue

        is_rebal = (last_rebal is None) or ((dt - last_rebal).days >= rb)
        if is_rebal:
            scores = {}
            for code in CORE:
                if dt in mom_63.index and code in mom_63.columns:
                    v = mom_63.loc[dt, code]
                    if not pd.isna(v):
                        scores[code] = v
            if not scores:
                holding = []
                continue
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            best = ranked[0]
            if best[1] > 0:
                holding = [best[0]]
                last_buy_date = dt
            else:
                holding = []
            last_rebal = dt

        if holding:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if holding[0] in pos_df.columns:
                pos_df.loc[dt, holding[0]] = w

    dr = panel.pct_change().fillna(0)
    ret = (dr * pos_df.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[1200])
    ret = ret[ret.index >= fs]
    if len(ret) >= 20:
        eq = (1 + ret).cumprod()
        cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
        sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
        mdd = ((eq - eq.cummax()) / eq.cummax()).min()
        print(f"  最低拿{min_hold:>3}d: CAGR={round(cagr*100,1):>5.1f}%  Sharpe={sp:.2f}  MDD={round(mdd*100,1):>5.1f}%")

print(f"\n{'='*75}")
print(f"  目标: 20%+  |  最佳: ...")
print(f"{'='*75}")
