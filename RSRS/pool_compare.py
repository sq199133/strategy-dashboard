"""
回测对比：当前13只池 vs 加入8只后的21只池
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

# ---- 扩展池 ----
EXTRA = {
    "510230": "FINANCE",
    "159915": "CYB",
    "159901": "SZ100",
    "512010": "MEDICAL",
    "512070": "SECURITY",
    "159939": "IT",
    "513100": "NASDAQ",
    "513500": "SP500",
}
NEW_POOL = {**DEFAULT_POOL, **EXTRA}

print("=" * 80)
print("  RSRS+C63 池子对比回测")
print(f"  参数: N={N} M={M} buy={BUY} sell={SELL} top={TOP} rb={RB} vw={VW} tv={TV}")
print("=" * 80)

def run_backtest(pool_dict, label):
    """单次回测"""
    data, panel = build_panel(pool_dict, min_rows=200)
    df510 = load_etf("510300")
    sig, zs, bt = compute_rsrs(df510, N, M, BUY, SELL)
    sig_dates = df510["date"].values
    mom_data = compute_momentum(data, panel)
    scale = compute_vol_scaling(df510, panel.index, VW, TV)
    positions = run_strategy(data, panel, sig, sig_dates, mom_data, RB, TOP, scale)

    daily_ret = panel.pct_change().fillna(0)
    ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)

    # 年度
    years = sorted(set(d.year for d in panel.index))
    annual = []
    for yr in years:
        mask = panel.index.year == yr
        nd = mask.sum()
        if nd < 10:
            continue
        yr_ret = ret[mask]
        yr_eq = (1 + yr_ret).cumprod()
        cagr = yr_eq.iloc[-1] ** (252 / nd) - 1
        sharpe = np.sqrt(252) * yr_ret.mean() / yr_ret.std() if yr_ret.std() > 1e-10 else 0
        mdd = ((yr_eq - yr_eq.cummax()) / yr_eq.cummax()).min()
        annual.append({"year": yr, "return": round(cagr * 100, 1), "sharpe": round(sharpe, 2), "mdd": round(mdd * 100, 1)})

    eq_total = (1 + ret).cumprod()
    cagr_total = eq_total.iloc[-1] ** (252 / len(ret)) - 1
    sharpe_total = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd_total = ((eq_total - eq_total.cummax()) / eq_total.cummax()).min()
    win_rate = (ret > 0).sum() / len(ret) * 100
    vol_scaling = scale.mean() if label == "新池" else scale.mean()

    return {
        "label": label,
        "n_etfs": len(pool_dict),
        "cagr": round(cagr_total * 100, 1),
        "sharpe": round(sharpe_total, 2),
        "mdd": round(mdd_total * 100, 1),
        "win_rate": round(win_rate, 1),
        "annual": annual,
        "total_days": len(ret),
    }

r1 = run_backtest(DEFAULT_POOL, "旧池(13只)")
r2 = run_backtest(NEW_POOL, "新池(21只)")

# ---- 打印对比 ----
print(f"\n  {'指标':<12}  {'旧池 13只':>12}  {'新池 21只':>12}  {'变化':>10}")
print(f"  {'-'*54}")
print(f"  {'年化收益%':<12}  {r1['cagr']:>12.1f}  {r2['cagr']:>12.1f}  {r2['cagr']-r1['cagr']:>+9.1f}")
print(f"  {'夏普比率':<12}  {r1['sharpe']:>12.2f}  {r2['sharpe']:>12.2f}  {r2['sharpe']-r1['sharpe']:>+9.2f}")
print(f"  {'最大回撤%':<12}  {r1['mdd']:>12.1f}  {r2['mdd']:>12.1f}  {r2['mdd']-r1['mdd']:>+9.1f}")
print(f"  {'胜率%':<12}  {r1['win_rate']:>12.1f}  {r2['win_rate']:>12.1f}  {r2['win_rate']-r1['win_rate']:>+9.1f}")
print(f"  {'交易日':<12}  {r1['total_days']:>12}  {r2['total_days']:>12}")
print(f"  {'ETF数量':<12}  {r1['n_etfs']:>12}  {r2['n_etfs']:>12}")

# 分年
years_all = sorted(set(y["year"] for y in r1["annual"] + r2["annual"]))
print(f"\n  {'年份':<6}  {'旧池收益':>9}  {'旧池夏普':>9}  {'新池收益':>9}  {'新池夏普':>9}  {'收益差':>8}")
print(f"  {'-'*59}")
for yr in years_all:
    a1 = next((x for x in r1["annual"] if x["year"] == yr), None)
    a2 = next((x for x in r2["annual"] if x["year"] == yr), None)
    if a1 and a2:
        diff = a2["return"] - a1["return"]
        print(f"  {yr:<6}  {a1['return']:>9.1f}%  {a1['sharpe']:>9.2f}  {a2['return']:>9.1f}%  {a2['sharpe']:>9.2f}  {diff:>+8.1f}%")
    elif a1:
        print(f"  {yr:<6}  {a1['return']:>9.1f}%  {a1['sharpe']:>9.2f}  {'-':>9}  {'-':>9}  {'-':>8}")
    else:
        print(f"  {yr:<6}  {'-':>9}  {'-':>9}  {a2['return']:>9.1f}%  {a2['sharpe']:>9.2f}")

result = {"old": r1, "new": r2}
with open("D:\\QClaw_Trading\\RSRS\\pool_compare.json", "w", encoding="utf-8") as f:
    # 转换numpy类型
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj
    json.dump(result, f, ensure_ascii=False, indent=2, default=convert)

print(f"\n[保存] pool_compare.json")
