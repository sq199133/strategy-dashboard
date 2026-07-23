#!/usr/bin/env python3
"""
ETF虚拟盘 v2.0 - 历史回测收益回顾
信号驱动型：三策略并行，每策略最多3只持仓
"""

import json, os, pandas as pd, numpy as np
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
PORTFOLIO_FILE = r"D:\QClaw_Trading\virtual_portfolio_v2.json"
INITIAL_TOTAL = 50000.0
INITIAL_PER_STRAT = 16666.67
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15
MAX_POSITIONS = 3

def load_etf(code):
    for prefix in ['sh', 'sz']:
        path = os.path.join(DATA_DIR, f"{prefix}{code}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'records' in data:
                df = pd.DataFrame(data['records'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                for col in ['close', 'high', 'low']:
                    df[col] = df[col].astype(float)
                return df
    return None

def calc(df):
    df = df.copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_u'] = df['ma20'] + 2 * df['std20']
    df['bb_l'] = df['ma20'] - 2 * df['std20']
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20l'] = df['close'].rolling(20).mean()
    df['high20'] = df['high'].rolling(20).max()
    df['low20'] = df['low'].rolling(20).min()
    return df

def backtest_strategy(candidates, strategy_name, init_capital):
    """回测单个策略，返回每日净值和交易记录"""
    cash = init_capital
    positions = []  # {code, name, shares, avg_cost, buy_date}
    nav_history = []  # [(date, nav), ...]
    all_trades = []   # 所有完整交易
    
    # 合并所有候选ETF的日期范围
    all_dfs = {}
    for c in candidates:
        df = load_etf(c['code'])
        if df is not None:
            all_dfs[c['code']] = df
    
    if not all_dfs:
        return None, []
    
    # 找共同日期范围
    start_dates = [df['date'].min() for df in all_dfs.values()]
    end_dates = [df['date'].max() for df in all_dfs.values()]
    common_start = max(start_dates)
    common_end = min(end_dates)
    
    # 合并所有数据到一个时间轴
    all_dates = sorted(set.union(*[set(df['date']) for df in all_dfs.values()]))
    all_dates = [d for d in all_dates if common_start <= d <= common_end]
    
    if len(all_dates) < 60:
        return None, []
    
    # 策略回测
    for current_date in all_dates:
        # 获取当天各ETF数据
        current_prices = {}
        for code, df in all_dfs.items():
            if current_date in df['date'].values:
                row = df[df['date'] == current_date].iloc[0]
                current_prices[code] = float(row['close'])
        
        # 计算当前账户净值
        pos_value = sum(p['shares'] * current_prices[p['code']] for p in positions if p['code'] in current_prices)
        total_value = cash + pos_value
        nav_history.append((current_date, total_value))
        
        # === 检查卖出 ===
        new_positions = []
        for pos in positions:
            code = pos['code']
            if code not in current_prices:
                new_positions.append(pos)
                continue
            
            c = current_prices[code]
            entry = pos['avg_cost']
            
            # 止损/止盈检查
            should_sell = False
            reason = ''
            if c < entry * (1 - STOP_LOSS):
                should_sell, reason = True, '止损'
            elif c > entry * (1 + TAKE_PROFIT):
                should_sell, reason = True, '止盈'
            
            # 信号检查
            if not should_sell:
                df = all_dfs[code]
                row_idx = df[df['date'] == current_date].index[0]
                if row_idx < 25:
                    new_positions.append(pos)
                    continue
                
                df_calc = calc(df.copy())
                i = row_idx
                
                if strategy_name == '布林带突破':
                    bb_l = float(df_calc['bb_l'].iloc[i])
                    bb_l_prev = float(df_calc['bb_l'].iloc[i-1])
                    prev_close = float(df_calc['close'].iloc[i-1])
                    if prev_close >= bb_l_prev and c < bb_l:
                        should_sell, reason = True, '信号卖出'
                elif strategy_name == '趋势突破':
                    low20 = float(df_calc['low20'].iloc[i])
                    low20_prev = float(df_calc['low20'].iloc[i-1])
                    prev_close = float(df_calc['close'].iloc[i-1])
                    if prev_close >= low20_prev and c < low20:
                        should_sell, reason = True, '信号卖出'
                elif strategy_name == '均线交叉':
                    ma5 = float(df_calc['ma5'].iloc[i])
                    ma20l = float(df_calc['ma20l'].iloc[i])
                    ma5_prev = float(df_calc['ma5'].iloc[i-1])
                    ma20l_prev = float(df_calc['ma20l'].iloc[i-1])
                    if ma5_prev >= ma20l_prev and ma5 < ma20l:
                        should_sell, reason = True, '信号卖出'
            
            if should_sell:
                ret_pct = (c / entry - 1) * 100
                cash += pos['shares'] * c
                all_trades.append({
                    'code': code, 'name': pos['name'],
                    'buy_date': pos['buy_date'], 'sell_date': str(current_date.date()),
                    'buy_price': entry, 'sell_price': c,
                    'shares': pos['shares'], 'return_pct': round(ret_pct, 2),
                    'reason': reason
                })
            else:
                new_positions.append(pos)
        
        positions = new_positions
        
        # === 检查买入 ===
        if len(positions) < MAX_POSITIONS:
            candidates_pool = [c for c in candidates if c['code'] not in {p['code'] for p in positions}]
            
            for c in candidates_pool:
                if len(positions) >= MAX_POSITIONS:
                    break
                code = c['code']
                if code not in current_prices:
                    continue
                
                c_price = current_prices[code]
                if c_price <= 0:
                    continue
                
                # 获取前一根K线数据判断信号
                df = all_dfs[code]
                if current_date not in df['date'].values:
                    continue
                row_idx = df[df['date'] == current_date].index[0]
                if row_idx < 25:
                    continue
                
                df_calc = calc(df.copy())
                i = row_idx
                
                buy_signal = False
                if strategy_name == '布林带突破':
                    bb_u = float(df_calc['bb_u'].iloc[i])
                    bb_u_prev = float(df_calc['bb_u'].iloc[i-1])
                    prev_close = float(df_calc['close'].iloc[i-1])
                    buy_signal = (prev_close <= bb_u_prev and c_price > bb_u_prev)
                elif strategy_name == '趋势突破':
                    high20 = float(df_calc['high20'].iloc[i])
                    high20_prev = float(df_calc['high20'].iloc[i-1])
                    prev_close = float(df_calc['close'].iloc[i-1])
                    buy_signal = (prev_close <= high20_prev and c_price > high20_prev)
                elif strategy_name == '均线交叉':
                    ma5 = float(df_calc['ma5'].iloc[i])
                    ma20l = float(df_calc['ma20l'].iloc[i])
                    ma5_prev = float(df_calc['ma5'].iloc[i-1])
                    ma20l_prev = float(df_calc['ma20l'].iloc[i-1])
                    buy_signal = (ma5_prev <= ma20l_prev and ma5 > ma20l)
                
                if buy_signal:
                    shares = int(cash / c_price * 0.995)
                    if shares > 0:
                        cash -= shares * c_price
                        positions.append({
                            'code': code, 'name': c['name'],
                            'shares': shares, 'avg_cost': c_price,
                            'buy_date': str(current_date.date())
                        })
    
    # 最终结算
    final_value = cash + sum(p['shares'] * current_prices.get(p['code'], p['avg_cost']) for p in positions if p['code'] in current_prices)
    
    # 计算年化收益率
    if len(nav_history) >= 2:
        start_val = nav_history[0][1]
        end_val = nav_history[-1][1]
        days = (nav_history[-1][0] - nav_history[0][0]).days
        annual_ret = (end_val / start_val - 1) * 365 / max(days, 1) * 100
    else:
        annual_ret = 0
    
    completed = [t for t in all_trades if t['reason'] in ['止损', '止盈', '信号卖出']]
    wins = [t for t in completed if t['return_pct'] > 0]
    
    return {
        'strategy': strategy_name,
        'init_capital': init_capital,
        'final_value': round(final_value, 2),
        'total_return_pct': round((final_value / init_capital - 1) * 100, 2),
        'annual_return_pct': round(annual_ret, 2),
        'trade_count': len(completed),
        'win_count': len(wins),
        'win_rate': round(len(wins) / len(completed) * 100, 1) if completed else 0,
        'max_win': round(max([t['return_pct'] for t in completed], default=0), 2),
        'max_loss': round(min([t['return_pct'] for t in completed], default=0), 2),
        'current_positions': len(positions),
        'start_date': str(nav_history[0][0].date()) if nav_history else None,
        'end_date': str(nav_history[-1][0].date()) if nav_history else None,
        'backtest_days': len(nav_history),
        'nav_history': [(str(d.date()), round(v, 2)) for d, v in nav_history]
    }, all_trades

# 主程序
with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
    portfolio = json.load(f)

results = {}
all_trades_global = []

print("开始回测...")
print(f"初始资金: {INITIAL_TOTAL:,.2f}元 (每策略 {INITIAL_PER_STRAT:,.2f}元)")
print()

for strat_name, strat in portfolio['strategies'].items():
    candidates = strat['candidates']
    print(f"回测中: 【{strat_name}】候选{candidates.__len__()}只...")
    
    result, trades = backtest_strategy(candidates, strat_name, INITIAL_PER_STRAT)
    results[strat_name] = result
    all_trades_global.extend(trades)
    
    if result:
        print(f"  ✓ 最终资产: {result['final_value']:,.2f}元")
        print(f"    总收益: {result['total_return_pct']:+.2f}%")
        print(f"    年化: {result['annual_return_pct']:+.2f}%")
        print(f"    交易次数: {result['trade_count']} | 胜率: {result['win_rate']:.0f}%")
        print(f"    最大单笔: {result['max_win']:+.1f}% | 最大亏损: {result['max_loss']:+.1f}%")
        print(f"    回测区间: {result['start_date']} ~ {result['end_date']} ({result['backtest_days']}个交易日)")
    else:
        print(f"  ✗ 数据不足，跳过")
    print()

# 汇总
total_final = sum(r['final_value'] for r in results.values() if r)
total_init = INITIAL_TOTAL
total_return = (total_final / total_init - 1) * 100

# 计算组合年化（加权）
total_days = max(r['backtest_days'] for r in results.values() if r) if results else 0
annual_return = (total_final / total_init - 1) * 365 / max(total_days, 1) * 100

# 汇总交易
all_completed = [t for t in all_trades_global if t['reason'] in ['止损', '止盈', '信号卖出']]
total_trades = len(all_completed)
total_wins = len([t for t in all_completed if t['return_pct'] > 0])
overall_win_rate = total_wins / total_trades * 100 if total_trades else 0

print(f"{'='*65}")
print(f"📊 虚拟盘 v2.0 历史回测汇总")
print(f"{'='*65}")
print(f"初始资金: {total_init:,.2f}元")
print(f"最终总资产: {total_final:,.2f}元")
print(f"累计收益: {total_return:+.2f}%")
print(f"年化收益: {annual_return:+.2f}%")
print(f"回测区间: {min(r['start_date'] for r in results.values() if r)} ~ {max(r['end_date'] for r in results.values() if r)}")
print()
print(f"{'策略':<12} {'最终资产':>10} {'总收益':>8} {'年化':>7} {'交易':>5} {'胜率':>6} {'最大赢':>7} {'最大亏':>7}")
print('-'*70)
for name, r in results.items():
    if r:
        print(f"{name:<12} {r['final_value']:>10,.0f} {r['total_return_pct']:>+7.1f}% {r['annual_return_pct']:>+6.1f}% {r['trade_count']:>4}次 {r['win_rate']:>5.0f}% {r['max_win']:>+6.1f}% {r['max_loss']:>+6.1f}%")
print('-'*70)
print(f"{'合计':<12} {total_final:>10,.0f} {total_return:>+7.1f}% {annual_return:>+6.1f}% {total_trades:>4}次 {overall_win_rate:>5.0f}%", end="")
if all_completed:
    print(f" {max(t['return_pct'] for t in all_completed):>+6.1f}% {min(t['return_pct'] for t in all_completed):>+6.1f}%")
else:
    print()

# 保存结果
output = {
    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'initial_capital': total_init,
    'final_capital': round(total_final, 2),
    'total_return_pct': round(total_return, 2),
    'annual_return_pct': round(annual_return, 2),
    'backtest_summary': {
        'start_date': min(r['start_date'] for r in results.values() if r),
        'end_date': max(r['end_date'] for r in results.values() if r),
        'total_trading_days': total_days,
        'total_trades': total_trades,
        'overall_win_rate': round(overall_win_rate, 1)
    },
    'strategies': results,
    'all_trades': all_trades_global
}

with open(r"D:\QClaw_Trading\data\virtual_backtest_v2.json", 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ 回测结果已保存: virtual_backtest_v2.json")
print(f"📋 详细交易记录: {len(all_trades_global)}笔")