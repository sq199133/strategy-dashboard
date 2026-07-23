"""
纯A股宽基 + 黄金 vs 原池
排除国际标的使RSRS择时逻辑一致
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy, DEFAULT_POOL)

N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

def run_backtest(pool_dict, label, rsrs_code="510300"):
    data, panel = build_panel(pool_dict, min_rows=200)
    df = load_etf(rsrs_code)
    sig, zs, bt = compute_rsrs(df, N, M, BUY, SELL)
    sig_dates = df["date"].values
    mom_data = compute_momentum(data, panel)
    scale = compute_vol_scaling(df, panel.index, VW, TV)
    positions = run_strategy(data, panel, sig, sig_dates, mom_data, RB, TOP, scale)

    daily_ret = panel.pct_change().fillna(0)
    ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)
    eq = (1 + ret).cumprod()

    years = sorted(set(d.year for d in panel.index))
    annual = []
    for yr in years:
        mask = panel.index.year == yr
        nd = mask.sum()
        if nd < 10: continue
        yr_ret = ret[mask]
        yr_eq = (1 + yr_ret).cumprod()
        cagr = yr_eq.iloc[-1] ** (252 / nd) - 1
        sharpe = np.sqrt(252) * yr_ret.mean() / yr_ret.std() if yr_ret.std() > 1e-10 else 0
        mdd = ((yr_eq - yr_eq.cummax()) / yr_eq.cummax()).min()
        annual.append({"year": yr, "cagr": round(cagr*100,1), "sharpe": round(sharpe,2), "mdd": round(mdd*100,1)})

    cagr_total = eq.iloc[-1] ** (252 / len(ret)) - 1
    sharpe_total = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd_total = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100

    return {"label": label, "n": len(pool_dict),
            "cagr": round(cagr_total*100,1), "sharpe": round(sharpe_total,2),
            "mdd": round(mdd_total*100,1), "win_rate": round(wr,1),
            "annual": annual, "days": len(ret)}

# 版本0: 原池（基线）
r_old = run_backtest(DEFAULT_POOL, "原池(含行业)")

# 版本1: 纯A股宽基(无海外) + 黄金
pool_a = {
    "510050": "SH50",      # 上证50
    "510300": "HS300",     # 沪深300
    "159915": "CYB",       # 创业板指
    "159902": "ZZSM100",   # 中小100
    "512100": "ZZ1000",    # 中证1000
    "518880": "GOLD",      # 黄金ETF
}
r_a = run_backtest(pool_a, "A股宽基+黄金")

# 版本2: A股宽基 + 黄金 + 创业板50(替换创业板指)
pool_b = {
    "510050": "SH50",
    "510300": "HS300",
    "159949": "CYB50",     # 创业板50 (替代创业板指)
    "159902": "ZZSM100",
    "512100": "ZZ1000",
    "518880": "GOLD",
}
r_b = run_backtest(pool_b, "A股宽基(CYB50)+黄金")

# 版本3: A股宽基 + 黄金 + 创业板50 + 创业板指
pool_c = {**pool_b, "159915": "CYB"}
r_c = run_backtest(pool_c, "A股宽基(全)")

results = [r_old, r_a, r_b, r_c]

print(f"  参数: N={N} M={M} buy={BUY} sell={SELL} top={TOP} rb={RB} vw={VW}\n")
print(f"  {'方案':<24}  {'CAGR%':>7}  {'夏普':>5}  {'MDD%':>6}  {'胜率%':>5}  {'ETF数':>5}")
print(f"  {'-'*60}")
for r in results:
    print(f"  {r['label']:<24}  {r['cagr']:>7.1f}%  {r['sharpe']:>5.2f}  {r['mdd']:>6.1f}%  {r['win_rate']:>5.1f}%  {r['n']:>5}")

# 分年对比
print(f"\n  {'年份':<5}  {'原池':>7}  {'A股宽基+金':>9}  {'B:宽基CYB50':>9}  {'C:宽基全':>9}")
print(f"  {'-'*50}")
years_all = sorted(set(y["year"] for r in results for y in r["annual"]))
for yr in years_all:
    line = f"  {yr:<5}"
    for r in results:
        a = next((x for x in r["annual"] if x["year"]==yr), None)
        line += f"  {a['cagr']:>7.1f}%" if a else "  "+" "*8
    print(line)
