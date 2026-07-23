"""
每年收益、胜率、仓位 综合统计
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

print(f"{'='*85}")
print(f"  RSRS+C63+波动率 年度综合统计（全池13只）")
print(f"{'='*85}")

# 加载
data, panel = build_panel(DEFAULT_POOL, min_rows=200)
df510 = load_etf("510300")
sig, _, _ = compute_rsrs(df510, N, M, BUY, SELL)
sig_dates = df510["date"].values
mom_data = compute_momentum(data, panel)
scale = compute_vol_scaling(df510, panel.index, VW, TV)
positions = run_strategy(data, panel, sig, sig_dates, mom_data, RB, TOP, scale)

daily_ret = panel.pct_change().fillna(0)
strat_ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)

# 每年统计
years = sorted(set(d.year for d in panel.index))

rows = []
for yr in years:
    mask = panel.index.year == yr
    nd = mask.sum()
    if nd < 10:
        continue
    
    ys = strat_ret[mask]
    yeq = (1 + ys).cumprod()
    
    # 年化收益
    cagr = yeq.iloc[-1] ** (252 / nd) - 1
    
    # 夏普
    sharpe = np.sqrt(252) * ys.mean() / ys.std() if ys.std() > 1e-10 else 0
    
    # 最大回撤
    mdd = ((yeq - yeq.cummax()) / yeq.cummax()).min()
    
    # 胜率 = 正收益天数占比
    win_rate = (ys > 0).sum() / nd * 100
    
    # 平均仓位（持仓日的仓位均值）
    pos_yr = positions[mask]
    daily_pos = pos_yr.sum(axis=1)
    avg_position = daily_pos[daily_pos > 0].mean() if (daily_pos > 0).any() else 0
    
    # 持仓天数占比
    holding_pct = (daily_pos > 0).sum() / nd * 100
    
    # 正周率
    weekly_ret = ys.resample('W-FRI').apply(lambda x: (1+x).prod()-1)
    week_win = (weekly_ret.dropna() > 0).sum()
    week_total = len(weekly_ret.dropna())
    week_win_rate = week_win / week_total * 100 if week_total > 0 else 0
    
    # 最大单日涨幅/跌幅
    best_day = ys.max() * 100
    worst_day = ys.min() * 100
    
    # 盈利总金额比例 (cumulative)
    total_profit = yeq.iloc[-1] - 1
    
    rows.append({
        "Year": yr,
        "Days": nd,
        "CAGR%": round(cagr * 100, 1),
        "Sharpe": round(sharpe, 2),
        "MDD%": round(mdd * 100, 1),
        "WinRate%": round(win_rate, 1),
        "WeekWin%": round(week_win_rate, 1),
        "AvgPos%": round(avg_position * 100, 1),
        "Hold%": round(holding_pct, 1),
        "BestDay%": round(best_day, 1),
        "WorstDay%": round(worst_day, 1),
    })

# 合计
ys_all = strat_ret
yeq_all = (1 + ys_all).cumprod()
cagr_all = yeq_all.iloc[-1] ** (252 / len(ys_all)) - 1
sharpe_all = np.sqrt(252) * ys_all.mean() / ys_all.std() if ys_all.std() > 1e-10 else 0
mdd_all = ((yeq_all - yeq_all.cummax()) / yeq_all.cummax()).min()
win_all = (ys_all > 0).sum() / len(ys_all) * 100
pos_all = positions.sum(axis=1)
avg_pos_all = pos_all[pos_all > 0].mean() if (pos_all > 0).any() else 0
holding_all = (pos_all > 0).sum() / len(pos_all) * 100
weekly_all = ys_all.resample("W-FRI").apply(lambda x: (1+x).prod()-1).dropna()
ww_all = (weekly_all > 0).sum() / len(weekly_all) * 100

total = {
    "Year": "TOTAL",
    "Days": len(ys_all),
    "CAGR%": round(cagr_all * 100, 1),
    "Sharpe": round(sharpe_all, 2),
    "MDD%": round(mdd_all * 100, 1),
    "WinRate%": round(win_all, 1),
    "WeekWin%": round(ww_all, 1),
    "AvgPos%": round(avg_pos_all * 100, 1),
    "Hold%": round(holding_all, 1),
    "BestDay%": round(ys_all.max() * 100, 1),
    "WorstDay%": round(ys_all.min() * 100, 1),
}

# ---- 打印 ----
print(f"\n{'='*85}")
print(f"  {'Year':<6} {'Days':<5} {'CAGR%':>7} {'Sharpe':>7} {'MDD%':>7}  "
      f"{'Win%':>5} {'WkWin%':>6} {'AvgPos%':>7} {'Hold%':>6} "
      f"{'BestD%':>7} {'WorstD%':>7}")
print(f"  {'-'*79}")

for r in rows:
    flag = " *" if r["Year"] == 2022 else "  "
    print(f"  {r['Year']:<6}{flag} {r['Days']:<5} {r['CAGR%']:>7.1f} {r['Sharpe']:>7.2f} {r['MDD%']:>7.1f}  "
          f"{r['WinRate%']:>5.1f} {r['WeekWin%']:>6.1f} {r['AvgPos%']:>7.1f} {r['Hold%']:>6.1f} "
          f"{r['BestDay%']:>7.1f} {r['WorstDay%']:>7.1f}")

print(f"  {'-'*79}")
t = total
print(f"  {t['Year']:<6}  {t['Days']:<5} {t['CAGR%']:>7.1f} {t['Sharpe']:>7.2f} {t['MDD%']:>7.1f}  "
      f"{t['WinRate%']:>5.1f} {t['WeekWin%']:>6.1f} {t['AvgPos%']:>7.1f} {t['Hold%']:>6.1f} "
      f"{t['BestDay%']:>7.1f} {t['WorstDay%']:>7.1f}")

print(f"   * 2022: 唯一亏损年份（震荡市）")
print(f"{'='*85}")

# 额外：波动率缩放每年均值
print(f"\n  --- 额外: 每年波动率缩放均值 ---")
print(f"  {'Year':<6} {'AvgScale':>9} {'MaxScale':>9} {'MinScale':>9} {'Full%':>7}")
for yr in years:
    mask = scale.index.year == yr
    if mask.sum() < 10:
        continue
    sy = scale[mask]
    full_pct = (sy >= 0.99).sum() / len(sy) * 100
    print(f"  {yr:<6} {sy.mean():>9.2f} {sy.max():>9.2f} {sy.min():>9.2f} {full_pct:>6.1f}%")
sy_all = scale
print(f"  {'TOTAL':<6} {sy_all.mean():>9.2f} {sy_all.max():>9.2f} {sy_all.min():>9.2f} {(sy_all>=0.99).sum()/len(sy_all)*100:>6.1f}%")

# 保存
out = {"years": rows, "total": total}
with open("D:\\QClaw_Trading\\RSRS\\annual_stats.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n[保存] annual_stats.json")
