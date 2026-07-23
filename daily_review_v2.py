#!/usr/bin/env python3
"""
ETF虚拟盘 v2.0 - 每日复盘脚本（修正版）
信号驱动型：每策略16,667元，每只ETF最大5,556元，每策略最多3只持仓
"""

import json, os, pandas as pd, numpy as np
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
PORTFOLIO_FILE = r"D:\QClaw_Trading\virtual_portfolio_v2.json"
OUTPUT_DIR = r"D:\QClaw_Trading\daily"
PER_ETF_CAPITAL = 5556.0
PER_STRATEGY_CAPITAL = 16667.0
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15
MAX_POSITIONS = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

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

def check_sell_logic(df, strategy, entry_price, latest_close):
    """检查是否触发卖出"""
    c = latest_close
    if c < entry_price * (1 - STOP_LOSS):
        return True, '止损'
    if c > entry_price * (1 + TAKE_PROFIT):
        return True, '止盈'
    
    df = calc(df.copy())
    i = len(df) - 1
    
    if strategy == '布林带突破':
        bb_l = float(df['bb_l'].iloc[i])
        bb_l_prev = float(df['bb_l'].iloc[i-1])
        if float(df['close'].iloc[i-1]) >= bb_l_prev and c < bb_l:
            return True, '信号卖出'
    elif strategy == '趋势突破':
        low20 = float(df['low20'].iloc[i])
        low20_prev = float(df['low20'].iloc[i-1])
        if float(df['close'].iloc[i-1]) >= low20_prev and c < low20:
            return True, '信号卖出'
    elif strategy == '均线交叉':
        ma5 = float(df['ma5'].iloc[i])
        ma20l = float(df['ma20l'].iloc[i])
        ma5_prev = float(df['ma5'].iloc[i-1])
        ma20l_prev = float(df['ma20l'].iloc[i-1])
        if ma5_prev >= ma20l_prev and ma5 < ma20l:
            return True, '信号卖出'
    return False, None

def run_daily_review(review_date=None):
    if review_date is None:
        review_date = date.today()
    else:
        review_date = datetime.strptime(str(review_date)[:10], '%Y-%m-%d').date()
    
    is_trade = review_date.weekday() < 5
    date_str = review_date.strftime('%Y-%m-%d')
    day_name = ['一','二','三','四','五','六','日'][review_date.weekday()]
    
    with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
        portfolio = json.load(f)
    
    report = {
        'review_date': date_str,
        'day': day_name,
        'is_trading_day': is_trade,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'strategies': {},
        'orders': [],
        'messages': []
    }
    
    print(f"{'='*65}")
    print(f"📅 复盘日期: {date_str}（周{day_name}）{'【交易日】' if is_trade else '【非交易日】'}")
    print(f"{'='*65}")
    
    for strat_name, strat in portfolio['strategies'].items():
        cash = strat['current_cash']
        positions = strat['positions']
        
        print(f"\n{'─'*65}")
        print(f"📂 【{strat_name}】 现金: {cash:,.2f}元 | 持仓: {len(positions)}只/最多3只 | 每只最大{PER_ETF_CAPITAL:,.0f}元")
        
        # ===== 检查卖出 =====
        sell_orders = []
        for pos in positions:
            code, name = pos['code'], pos['name']
            shares, entry = pos['shares'], pos['avg_cost']
            
            df = load_etf(code)
            if df is None:
                print(f"  ⚠️ {code} {name}: 数据缺失，跳过")
                continue
            
            latest = float(df['close'].iloc[-1])
            latest_date = str(df['date'].iloc[-1].date())
            
            should_sell, reason = check_sell_logic(df, strat_name, entry, latest)
            pnl_pct = (latest / entry - 1) * 100
            pnl_val = (latest - entry) * shares
            
            print(f"  📊 {code} {name} | 现价:{latest:.3f} | 成本:{entry:.3f} | 浮盈:{pnl_pct:+.1f}%({pnl_val:+,.0f}元)", end="")
            
            if should_sell:
                print(f" → 【{reason}】")
                sell_orders.append({**pos, 'price': latest, 'date': latest_date, 'reason': reason, 'pnl_pct': pnl_pct})
            else:
                print()
        
        # ===== 执行卖出 =====
        for o in sell_orders:
            proceeds = o['shares'] * o['price']
            ret = o['pnl_pct']
            cash += proceeds
            strat['current_cash'] += proceeds
            strat['positions'] = [p for p in strat['positions'] if p['code'] != o['code']]
            print(f"  ✅ 卖出: {o['code']} {o['name']} {o['shares']}股 @{o['price']:.3f} 收益:{ret:+.2f}%")
            report['orders'].append({
                'strategy': strat_name, 'action': 'SELL', 'code': o['code'],
                'name': o['name'], 'shares': o['shares'], 'price': o['price'],
                'return_pct': round(ret, 2), 'reason': o['reason']
            })
        
        # ===== 检查买入 =====
        if len(positions) < MAX_POSITIONS and is_trade:
            candidates = strat['candidates']
            held_codes = {p['code'] for p in positions}
            
            buy_candidates = []
            for c in candidates:
                if c['code'] in held_codes:
                    continue
                df = load_etf(c['code'])
                if df is None:
                    continue
                
                latest = float(df['close'].iloc[-1])
                latest_date = str(df['date'].iloc[-1].date())
                df_calc = calc(df.copy())
                i = len(df_calc) - 1
                
                signal = False
                if strat_name == '布林带突破':
                    bb_u = float(df_calc['bb_u'].iloc[i])
                    bb_u_prev = float(df_calc['bb_u'].iloc[i-1])
                    signal = float(df_calc['close'].iloc[i-1]) <= bb_u_prev and latest > bb_u_prev
                elif strat_name == '趋势突破':
                    high20_prev = float(df_calc['high20'].iloc[i-1])
                    signal = float(df_calc['close'].iloc[i-1]) <= high20_prev and latest > high20_prev
                elif strat_name == '均线交叉':
                    ma5 = float(df_calc['ma5'].iloc[i])
                    ma20l = float(df_calc['ma20l'].iloc[i])
                    ma5_prev = float(df_calc['ma5'].iloc[i-1])
                    ma20l_prev = float(df_calc['ma20l'].iloc[i-1])
                    signal = ma5_prev <= ma20l_prev and ma5 > ma20l
                
                if signal:
                    bb_u = round(float(df_calc['bb_u'].iloc[i]), 4) if 'bb_u' in df_calc.columns else None
                    high20 = round(float(df_calc['high20'].iloc[i]), 4) if 'high20' in df_calc.columns else None
                    buy_candidates.append({
                        'code': c['code'], 'name': c['name'],
                        'price': latest, 'date': latest_date,
                        'signal': strat_name, 'bb_u': bb_u, 'high20': high20
                    })
            
            # 按价格分配资金：每只最多PER_ETF_CAPITAL
            for b in buy_candidates:
                if len(positions) >= MAX_POSITIONS:
                    break
                budget = min(PER_ETF_CAPITAL, strat['current_cash'])
                if budget < b['price'] * 100:
                    print(f"  ⚠️ 资金不足买入 {b['code']}（需要{b['price']*100:.0f}元）")
                    continue
                
                shares = int(budget / b['price'] * 0.995)
                cost = shares * b['price']
                strat['current_cash'] -= cost
                positions.append({
                    'code': b['code'], 'name': b['name'],
                    'shares': shares, 'avg_cost': b['price'],
                    'buy_date': b['date'], 'signal': b['signal']
                })
                print(f"  🚀 买入: {b['code']} {b['name']} {shares}股 @{b['price']:.3f} 成本:{cost:,.2f}元")
                report['orders'].append({
                    'strategy': strat_name, 'action': 'BUY',
                    'code': b['code'], 'name': b['name'],
                    'shares': shares, 'price': b['price'], 'cost': round(cost, 2)
                })
            strat['positions'] = positions
        
        # 更新策略状态
        strat_value = strat['current_cash'] + sum(p['shares'] * p.get('current_price', p['avg_cost']) for p in strat['positions'])
        strat_ret = (strat_value / PER_STRATEGY_CAPITAL - 1) * 100
        strat['status'] = f"{len(strat['positions'])}只持仓" if strat['positions'] else "空仓"
        print(f"  💰 策略资产: {strat_value:,.2f}元 | 收益: {strat_ret:+.2f}%")
        
        report['strategies'][strat_name] = {
            'cash': round(strat['current_cash'], 2),
            'positions': strat['positions'],
            'position_count': len(strat['positions']),
            'strategy_return_pct': round(strat_ret, 2)
        }
    
    # 重新计算总资产
    total_value = sum(s['current_cash'] for s in portfolio['strategies'].values())
    for strat in portfolio['strategies'].values():
        for pos in strat['positions']:
            df = load_etf(pos['code'])
            if df is not None and not df.empty:
                pos['current_price'] = float(df['close'].iloc[-1])
                pos['last_date'] = str(df['date'].iloc[-1].date())
                total_value += pos['shares'] * pos['current_price']
    
    portfolio['cash'] = total_value
    portfolio['total_value'] = round(total_value, 2)
    portfolio['total_return_pct'] = round((total_value / portfolio['initial_capital'] - 1) * 100, 2)
    
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)
    
    report_file = os.path.join(OUTPUT_DIR, f"review_{date_str}.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*65}")
    print(f"📊 虚拟盘总览:")
    for name, strat in portfolio['strategies'].items():
        pos_str = ', '.join([f"{p['code']}({p['name']})" for p in strat['positions']]) or '空仓'
        print(f"   {name}: 现金{strat['current_cash']:,.0f}元 | {strat['status']} | {pos_str}")
    print(f"   总资产: {portfolio['total_value']:,.2f}元 | 累计收益: {portfolio['total_return_pct']:+.2f}%")
    print(f"{'='*65}")
    
    return report

if __name__ == "__main__":
    import sys
    from datetime import date
    review_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_daily_review(review_date)