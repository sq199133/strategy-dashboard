"""
2026年周度收益计算（全池13只）
"""
import json, os, sys, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling)

# 全池13只ETF全部有数据至2026-06-16
from rsrs_final_strategy import DEFAULT_POOL as POOL_2026

print('=' * 50)
print('  2026 周度收益计算 (全池13只)')
print('=' * 50)

# 参数
N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

# 加载
print('\n[1] 加载数据...')
data, panel = build_panel(POOL_2026, min_rows=200)
print(f'  面板: {len(panel)}个交易日  {panel.index[0].date()} ~ {panel.index[-1].date()}')

# 截取 2026
panel_2026 = panel[panel.index >= '2026-01-01'].copy()
print(f'  2026年: {len(panel_2026)}个交易日  {panel_2026.index[0].date()} ~ {panel_2026.index[-1].date()}')

if len(panel_2026) == 0:
    print('  ❌ 无2026年数据')
    sys.exit(1)

# RSRS
print('\n[2] RSRS信号...')
df510 = load_etf('510300')
sig, _, _ = compute_rsrs(df510, N, M, BUY, SELL)
sig_dates = df510['date'].values

# 动量
print('[3] C63动量...')
mom_data = compute_momentum(data, panel)

# 波动率
print('[4] 波动率缩放...')
scale = compute_vol_scaling(df510, panel.index, VW, TV)

# 回测（沿用修复后的 run_strategy）
print('[5] 回测运行...')
from rsrs_final_strategy import run_strategy
positions = run_strategy(data, panel, sig, sig_dates,
                          mom_data, RB, TOP, scale)

# 提取 2026 年
pos_2026 = positions[positions.index >= '2026-01-01'].copy()
prices_2026 = panel[panel.index >= '2026-01-01'].copy()

# 计算日收益率
daily_ret = prices_2026.pct_change().fillna(0)
strat_ret = (daily_ret * pos_2026.shift(1).fillna(0)).sum(axis=1)

# 累计净值
eq = (1 + strat_ret).cumprod()

# 按周聚合 (周五切割)
# 使用 ISO week 编号
weekly = pd.DataFrame({
    'date': strat_ret.index,
    'daily_ret': strat_ret.values,
    'equity': eq.values,
})
weekly['week'] = weekly['date'].dt.isocalendar().year.astype(str) + '-W' + weekly['date'].dt.isocalendar().week.astype(str).str.zfill(2)

# 周度统计
weekly_stats = weekly.groupby('week').agg(
    first_date=('date', 'first'),
    last_date=('date', 'last'),
    week_return=('daily_ret', lambda x: (1 + x).prod() - 1),
    days=('date', 'count'),
    max_equity=('equity', 'max'),
).reset_index()

# 判断是否有持仓
hold_weeks = []
for d in pos_2026.index:
    held = (pos_2026.loc[d].sum() > 0)
    hold_weeks.append(held)
weekly['holding'] = hold_weeks
hold_by_week = weekly.groupby('week')['holding'].any()

# 输出
print(f'\n{"="*70}')
print(f'  2026年 周度收益明细 (截至 {panel_2026.index[-1].date()})')
print(f'{"="*70}')
print(f'  {"周":<12} {"日期":<14} {"周收益%":>8} {"累计净值":>10} {"持仓":>6} {"天数":>4}')
print(f'  {"-"*58}')

total_ret_2026 = 1.0
for _, r in weekly_stats.iterrows():
    w = r['week']
    h = 'Y' if hold_by_week.get(w, False) else '-'
    ret_pct = r['week_return'] * 100
    total_ret_2026 *= (1 + r['week_return'])
    dt_range = f"{r['first_date'].strftime('%m-%d')}~{r['last_date'].strftime('%m-%d')}"
    print(f'  {w:<10} {dt_range:<14} {ret_pct:>+7.2f}%  {r["max_equity"]:>10.4f}  {h:>4} {r["days"]:>4}')

# 汇总
first_date = weekly_stats['first_date'].iloc[0]
last_date = weekly_stats['last_date'].iloc[-1]
total_return = (total_ret_2026 - 1) * 100
cagr = total_ret_2026 ** (252 / len(strat_ret)) - 1
sharpe = np.sqrt(252) * strat_ret.mean() / strat_ret.std() if strat_ret.std() > 1e-10 else 0
mdd = ((eq - eq.cummax()) / eq.cummax()).min()

print(f'  {"-"*58}')
print(f'\n  ──── 2026年汇总 ────')
print(f'    区间: {first_date} ~ {last_date}')
print(f'    累计收益: {total_return:.1f}%')
print(f'    年化收益: {cagr*100:.1f}%')
print(f'    夏普比:   {sharpe:.2f}')
print(f'    最大回撤: {mdd*100:.1f}%')
print(f'    持仓天数: {hold_by_week.sum()}/{len(hold_by_week)} 周')

# 保存
out = {
    'pool': list(POOL_2026.keys()),
    'params': {'N': N, 'M': M, 'buy': BUY, 'sell': SELL, 'top': TOP, 'rb': RB},
    'weekly': [{
        'week': r['week'],
        'from': r['first_date'].strftime('%Y-%m-%d'),
        'to': r['last_date'].strftime('%Y-%m-%d'),
        'return_pct': round(r['week_return'] * 100, 2),
        'holding': bool(hold_by_week.get(r['week'], False)),
        'days': int(r['days']),
    } for _, r in weekly_stats.iterrows()],
    'summary': {
        'period': f'{first_date} ~ {last_date}',
        'total_return_pct': round(total_return, 1),
        'annualized_pct': round(cagr*100, 1),
        'sharpe': round(sharpe, 2),
        'max_drawdown_pct': round(mdd*100, 1),
    }
}
with open('D:\\QClaw_Trading\\RSRS\\weekly_2026_results.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f'\n[Saved] weekly_2026_results.json')
