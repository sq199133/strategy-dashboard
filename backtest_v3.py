#!/usr/bin/env python3
"""
ETF虚拟盘 v2.0 - 历史回测 v3（独立起始期）
每只ETF从自身数据起始日开始回测，不要求共同起点
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

def backtest_etf(code, name, strategy_name, init_capital):
    """回测单只ETF，返回结果和交易列表"""
    df = load_etf(code)
    if df is None or len(df) < 26:
        return None, []
    
    df = calc(df)
    
    cash = init_capital
    positions = []
    nav_history = []
    trades = []
    
    all_dates = sorted(df['date'].tolist())
    start_date = all_dates[0]
    end_date = all_dates[-1]
    
    for i, current_date in enumerate(all_dates):
        row = df[df['date'] == current_date]
        if row.empty:
            continue
        c = float(row['close'].iloc[0])
        
        # 净值
        pos_value = 0
        for p in positions:
            row_p = df[df['date'] == current_date]
            if not row_p.empty:
                pos_value += p['shares'] * float(row_p['close'].iloc[0])
            else:
                pos_value += p['shares'] * p['avg_cost']
        total_val = cash + pos_value
        nav_history.append((current_date, total_val))
        
        # === 卖出 ===
        new_positions = []
        for pos in positions:
            if i < 1:
                new_positions.append(pos)
                continue
            
            entry = pos['avg_cost']
            should_sell = False
            reason = ''
            
            # 止损/止盈
            if c < entry * (1 - STOP_LOSS):
                should_sell, reason = True, '止损'
            elif c > entry * (1 + TAKE_PROFIT):
                should_sell, reason = True, '止盈'
            
            # 信号卖出
            if not should_sell and i >= 25:
                if strategy_name == '布林带突破':
                    bb_l = float(df['bb_l'].iloc[i])
                    bb_l_prev = float(df['bb_l'].iloc[i-1])
                    prev_c = float(df['close'].iloc[i-1])
                    if prev_c >= bb_l_prev and c < bb_l:
                        should_sell, reason = True, '信号卖出'
                elif strategy_name == '趋势突破':
                    low20 = float(df['low20'].iloc[i])
                    low20_prev = float(df['low20'].iloc[i-1])
                    prev_c = float(df['close'].iloc[i-1])
                    if prev_c >= low20_prev and c < low20:
                        should_sell, reason = True, '信号卖出'
                elif strategy_name == '均线交叉':
                    ma5 = float(df['ma5'].iloc[i])
                    ma20l = float(df['ma20l'].iloc[i])
                    ma5_prev = float(df['ma5'].iloc[i-1])
                    ma20l_prev = float(df['ma20l'].iloc[i-1])
                    if ma5_prev >= ma20l_prev and ma5 < ma20l:
                        should_sell, reason = True, '信号卖出'
            
            if should_sell:
                ret_pct = (c / entry - 1) * 100
                cash += pos['shares'] * c
                trades.append({
                    'code': code, 'name': name,
                    'buy_date': pos['buy_date'], 'sell_date': str(current_date.date()),
                    'buy_price': entry, 'sell_price': c,
                    'shares': pos['shares'], 'return_pct': round(ret_pct, 2),
                    'reason': reason
                })
            else:
                new_positions.append(pos)
        
        positions = new_positions
        
        # === 买入 ===
        if len(positions) < MAX_POSITIONS and i >= 25:
            candidates_pool = [code]  # 只测试当前ETF
            for c_code in candidates_pool:
                if c_code != code:
                    continue
                if c_code in {p['code'] for p in positions}:
                    continue
                if c <= 0:
                    continue
                
                buy_signal = False
                if strategy_name == '布林带突破':
                    bb_u = float(df['bb_u'].iloc[i])
                    bb_u_prev = float(df['bb_u'].iloc[i-1])
                    prev_c = float(df['close'].iloc[i-1])
                    buy_signal = (prev_c <= bb_u_prev and c > bb_u_prev)
                elif strategy_name == '趋势突破':
                    high20 = float(df['high20'].iloc[i])
                    high20_prev = float(df['high20'].iloc[i-1])
                    prev_c = float(df['close'].iloc[i-1])
                    buy_signal = (prev_c <= high20_prev and c > high20_prev)
                elif strategy_name == '均线交叉':
                    ma5 = float(df['ma5'].iloc[i])
                    ma20l = float(df['ma20l'].iloc[i])
                    ma5_prev = float(df['ma5'].iloc[i-1])
                    ma20l_prev = float(df['ma20l'].iloc[i-1])
                    buy_signal = (ma5_prev <= ma20l_prev and ma5 > ma20l)
                
                if buy_signal:
                    shares = int(cash / c * 0.995)
                    if shares > 0:
                        cash -= shares * c
                        positions.append({
                            'code': code, 'name': name,
                            'shares': shares, 'avg_cost': c,
                            'buy_date': str(current_date.date())
                        })
    
    # 最终净值
    if nav_history:
        final_val = nav_history[-1][1]
        start_val = nav_history[0][1]
        days = (nav_history[-1][0] - nav_history[0][0]).days
        annual_ret = (final_val / start_val - 1) * 365 / max(days, 1) * 100
        
        completed = [t for t in trades if t['reason'] in ['止损', '止盈', '信号卖出']]
        wins = [t for t in completed if t['return_pct'] > 0]
        
        return {
            'code': code, 'name': name,
            'start_date': str(start_date.date()),
            'end_date': str(end_date.date()),
            'backtest_days': len(nav_history),
            'init_capital': init_capital,
            'final_value': round(final_val, 2),
            'total_return_pct': round((final_val / init_capital - 1) * 100, 2),
            'annual_return_pct': round(annual_ret, 2),
            'trade_count': len(completed),
            'win_count': len(wins),
            'win_rate': round(len(wins) / len(completed) * 100, 1) if completed else 0,
            'avg_return': round(sum(t['return_pct'] for t in completed) / len(completed), 2) if completed else 0,
            'max_win': round(max([t['return_pct'] for t in completed], default=0), 2),
            'max_loss': round(min([t['return_pct'] for t in completed], default=0), 2),
        }, trades
    return None, []

# 主程序
with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
    portfolio = json.load(f)

all_results = {}
all_trades = []

for strat_name, strat in portfolio['strategies'].items():
    candidates = strat['candidates']
    print(f"\n{'='*65}")
    print(f"回测: 【{strat_name}】 候选{candidates.__len__()}只")
    print(f"{'代码':<8} {'名称':<18} {'起始':<12} {'最终资产':>9} {'总收益':>7} {'年化':>6} {'交易':>4} {'胜率':>5} {'最大亏':>6}")
    print('-'*75)
    
    strat_etf_results = []
    
    for c in candidates:
        result, trades = backtest_etf(c['code'], c['name'], strat_name, INITIAL_PER_STRAT)
        
        if result:
            strat_etf_results.append(result)
            all_trades.extend(trades)
            print(f"  {c['code']:<8} {c['name']:<18} {result['start_date']:<12} {result['final_value']:>9,.0f} {result['total_return_pct']:>+6.1f}% {result['annual_return_pct']:>+5.1f}% {result['trade_count']:>4}次 {result['win_rate']:>4.0f}% {result['max_loss']:>+5.1f}%")
        else:
            print(f"  {c['code']:<8} {c['name']:<18} 数据不足或太短")
    
    # 策略汇总
    if strat_etf_results:
        avg_return = sum(r['total_return_pct'] for r in strat_etf_results) / len(strat_etf_results)
        avg_annual = sum(r['annual_return_pct'] for r in strat_etf_results) / len(strat_etf_results)
        avg_win_rate = sum(r['win_rate'] for r in strat_etf_results) / len(strat_etf_results)
        avg_trades = sum(r['trade_count'] for r in strat_etf_results) / len(strat_etf_results)
        earliest = min(r['start_date'] for r in strat_etf_results)
        latest = max(r['end_date'] for r in strat_etf_results)
        
        # 加权年化（按回测天数加权）
        weighted_annual = sum(r['annual_return_pct'] * r['backtest_days'] for r in strat_etf_results) / sum(r['backtest_days'] for r in strat_etf_results)
        
        print('-'*75)
        print(f"  【{strat_name}】汇总: {len(strat_etf_results)}只ETF有效 | 平均收益:{avg_return:+.1f}% | 加权年化:{weighted_annual:+.1f}%")
        print(f"  数据覆盖: {earliest} ~ {latest}")
        
        all_results[strat_name] = {
            'etf_count': len(strat_etf_results),
            'avg_return': round(avg_return, 2),
            'avg_annual': round(avg_annual, 2),
            'weighted_annual': round(weighted_annual, 2),
            'avg_win_rate': round(avg_win_rate, 1),
            'avg_trades': round(avg_trades, 1),
            'earliest_start': earliest,
            'latest_end': latest,
            'etf_results': strat_etf_results
        }

# 总览
print(f"\n{'='*65}")
print(f"📊 虚拟盘 v2.0 历史回测汇总（独立起始期）")
print(f"{'='*65}")
print(f"{'策略':<12} {'ETF数':>5} {'平均总收益':>9} {'加权年化':>8} {'平均胜率':>7} {'平均交易':>8} {'数据区间'}")
print('-'*90)
for name, r in all_results.items():
    print(f"{name:<12} {r['etf_count']:>5} {r['avg_return']:>+8.1f}% {r['weighted_annual']:>+7.1f}% {r['avg_win_rate']:>6.0f}% {r['avg_trades']:>7.1f}次  {r['earliest_start']} ~ {r['latest_end']}")

# 保存
output = {
    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'method': 'independent_start_per_etf',
    'initial_capital_per_etf': INITIAL_PER_STRAT,
    'strategies': all_results,
    'all_trades': all_trades
}
with open(r"D:\QClaw_Trading\data\virtual_backtest_v3.json", 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已保存: virtual_backtest_v3.json")