"""比较剔除162411(原油)的影响"""
import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS\current')
sys.stdout.reconfigure(encoding='utf-8')

from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_rsrs, compute_vol_scaling

POOL_ALL = {'510050':'SH50','510300':'HS300','510500':'ZZ500',
            '512100':'ZZ1000','159915':'CYB','588000':'KC50',
            '513500':'SP500','513100':'NSDQ','518880':'GOLD',
            '162411':'OIL','515080':'ZZHL'}

def run_bt(pool, M=1200, buy=0.7, sell=-1.0, rb=63, lock=42, no_neg=True):
    raw, panel = build_panel(pool, min_rows=200)
    if panel is None or len(panel) < 100:
        return None
    df_sig = load_etf('510300')
    if df_sig is None: return None
    sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)
    
    mom = {}
    for code, df in raw.items():
        s = df.set_index('date')['close'].pct_change(63)
        if s is not None:
            mom[code] = s[s.index.isin(panel.index)]
    
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig['date'].values))
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = int(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0:
            eff = 1
        if eff == 0:
            hold, lku = [], None
            continue
        if lock > 0 and raw_s == 1 and lku is None:
            lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= rb:
            scs = {}
            for c in pool:
                if dt in mom.get(c, pd.Series(dtype=float)).index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c,v in rk if v>0] if no_neg else [c for c,v in rk]
            hold = sel[:1] if sel else []
            lr = dt
        if hold and hold[0] in pos.columns:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            pos.loc[dt, hold[0]] = w
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig['date'].iloc[M])
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
    
    # Oil stats
    oil_hold, oil_chg = 0, 0
    if '162411' in pos.columns:
        oil_hold = (pos['162411'] > 0).mean() * 100
        oil_chg = int((pos['162411'].diff().abs() > 0.01).sum())
    
    return {'CAGR': round(cagr*100,1), 'Sharpe': round(sp,2),
            'MDD': round(mdd*100,1), 'W%': round(wr,1), 'Pos%': round(pr,1),
            'Annual': annual, 'OilHold%': oil_hold, 'OilChanges': oil_chg,
            'N_ETF': len(pool), 'TotalRet': round((float(eq.iloc[-1])-1)*100,1)}

print("=" * 60)
print("【剔除原油对比】参数: M=1200 buy=0.7 sell=-1.0 RB=63 lock=42")
print("=" * 60)

r_all = run_bt(POOL_ALL)
r_no = run_bt({k:v for k,v in POOL_ALL.items() if k != '162411'})

print()
print(f"{'指标':<15} {'11只(含油)':<18} {'10只(剔除)':<18} {'Δ':<10}")
print("-" * 55)
for k in ['CAGR','Sharpe','MDD','W%','Pos%','TotalRet']:
    v1 = r_all.get(k, 'N/A') if r_all else 'N/A'
    v2 = r_no.get(k, 'N/A') if r_no else 'N/A'
    diff = ''
    if isinstance(v1, (int,float)) and isinstance(v2, (int,float)):
        if k in ('Sharpe',):
            diff = f'{v2-v1:+.2f}'
        else:
            diff = f'{v2-v1:+.1f}'
    print(f"{k:<15} {str(v1):<18} {str(v2):<18} {diff:<10}")

print()
if r_all:
    print(f"含油池中 OIL持仓率: {r_all['OilHold%']:.1f}%  (调仓选中 {r_all['OilChanges']} 次)")

# Annual breakdown
if r_all and r_no:
    print()
    print(f"{'年':>6}  {'含油':>8}  {'剔除':>8}  {'Δ':>8}")
    print("-" * 34)
    all_yrs = sorted(set(list(r_all['Annual'].keys()) + list(r_no['Annual'].keys())))
    for yr in all_yrs:
        va = r_all['Annual'].get(yr, 0)
        vn = r_no['Annual'].get(yr, 0)
        print(f"{yr:>6}  {va:>7.1f}%  {vn:>7.1f}%  {vn-va:>+7.1f}%")

print()
print(f"结论: 剔除原油后 CAGR {'提升' if r_no and r_all and r_no['CAGR'] > r_all['CAGR'] else '下降'}了 ", end="")
if r_no and r_all:
    d = r_no['CAGR'] - r_all['CAGR']
    print(f"{abs(d):.1f}%")
print("=" * 60)
