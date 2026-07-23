"""
幸存者偏差检验：只用宽基指数+海外+商品
完全避免人为选品种
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy,
                                 analyze_performance, DEFAULT_POOL)

N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

# 仅宽基+海外+商品，无任何行业ETF
INDICES_POOL = {
    "510050": "SH50",      # 上证50 - 20年
    "510300": "HS300",     # 沪深300 - 14年
    "159915": "CYB",       # 创业板指 - 14年 (非CYB50)
    "159902": "ZZSM100",   # 中小100 - 19年
    "512100": "ZZ1000",    # 中证1000 - 9年
    "513100": "NASDAQ",    # 纳指ETF - 12年
    "513500": "SP500",     # 标普500ETF - 12年
    "518880": "GOLD",      # 黄金ETF - 12年
}

def run_backtest(pool_dict, label):
    data, panel = build_panel(pool_dict, min_rows=200)
    df510 = load_etf("510300")
    sig, zs, bt = compute_rsrs(df510, N, M, BUY, SELL)
    sig_dates = df510["date"].values
    mom_data = compute_momentum(data, panel)
    scale = compute_vol_scaling(df510, panel.index, VW, TV)
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
        annual.append({"year": yr, "return": round(cagr * 100, 1), "sharpe": round(sharpe, 2), "mdd": round(mdd * 100, 1)})

    cagr_total = eq.iloc[-1] ** (252 / len(ret)) - 1
    sharpe_total = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd_total = ((eq - eq.cummax()) / eq.cummax()).min()
    win_rate = (ret > 0).sum() / len(ret) * 100

    return {"label": label, "n": len(pool_dict), "cagr": round(cagr_total * 100, 1),
            "sharpe": round(sharpe_total, 2), "mdd": round(mdd_total * 100, 1),
            "win_rate": round(win_rate, 1), "annual": annual, "days": len(ret)}

print(f"  参数: N={N} M={M} buy={BUY} sell={SELL} top={TOP} rb={RB}")
print(f"  {'-'*70}\n")

r_old = run_backtest(DEFAULT_POOL, "老池(含行业)")
r_new = run_backtest(INDICES_POOL, "宽基池(无行业)")

print(f"  {'指标':<14}  {'老池(含行业)':>14}  {'宽基池(无行业)':>14}  {'差距':>10}")
print(f"  {'-'*58}")
for k in ["cagr","sharpe","mdd","win_rate","n"]:
    v1, v2 = r_old[k], r_new[k]
    suf = "%" if k in ("cagr","mdd","win_rate") else ""
    suf2 = "%" if k in ("mdd","win_rate") else ""
    diff = v2 - v1
    print(f"  {k:<14}  {v1:>12.1f}{suf}  {v2:>12.1f}{suf}  {diff:>+9.1f}")

# 分年
years_all = sorted(set(y["year"] for y in r_old["annual"] + r_new["annual"]))
print(f"\n  {'年份':<6}  {'老池':>8}  {'宽基池':>8}  {'差距':>8}  {'宽基夏普':>9}")
print(f"  {'-'*50}")
for yr in years_all:
    a1 = next((x for x in r_old["annual"] if x["year"]==yr), None)
    a2 = next((x for x in r_new["annual"] if x["year"]==yr), None)
    if a1 and a2:
        diff = a2["return"] - a1["return"]
        print(f"  {yr:<6}  {a1['return']:>7.1f}%  {a2['return']:>7.1f}%  {diff:>+7.1f}%  {a2['sharpe']:>8.2f}")
    elif a1:
        print(f"  {yr:<6}  {a1['return']:>7.1f}%  {'-':>8}  {'-':>8}")
    else:
        print(f"  {yr:<6}  {'-':>8}  {a2['return']:>7.1f}%  {'-':>8}  {a2['sharpe']:>8.2f}")

print(f"\n  {'='*60}")
if r_new["cagr"] >= r_old["cagr"] * 0.6:
    print(f"  结论：宽基池年化{r_new['cagr']}%，老池{r_old['cagr']}%，差距在合理范围")
    print(f"  策略对池子构成的依赖可控，幸存者偏差不严重")
else:
    print(f"  结论：宽基池年化{r_new['cagr']}% << 老池{r_old['cagr']}%")
    print(f"  幸存者偏差严重！策略收益高度依赖人工选品种")
print(f"  {'='*60}")
