#!/usr/bin/env python3
"""对比ETF池大小（3只 vs 10只）的N=1全仓轮换收益"""
import json, sys, os
import numpy as np
import pandas as pd

DATA_DIR   = r"D:\QClaw_Trading\data\history"
INIT_CAP   = 100000
STOP_LOSS  = 0.08
TAKE_PROFIT = 0.15
FEE_RATE   = 0.0005

# ============ 读取候选ETF ============
with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json', 'r', encoding='utf-8') as f:
    CANDIDATES = json.load(f)

# 结构: {all_results: {bollinger: [{code, total_return,...}], ...}}
# 取每个策略TOP N
def get_top_etfs(strategy, n):
    items = sorted(CANDIDATES['all_results'][strategy], key=lambda x: x['total_return'], reverse=True)
    return [it['code'] for it in items[:n]]

# ============ 数据加载 ============
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
                df['close'] = df['close'].astype(float)
                df['high']  = df['high'].astype(float)
                df['low']   = df['low'].astype(float)
                return df
    return None

def calculate_indicators(df):
    df['ma20']      = df['close'].rolling(20).mean()
    df['std20']     = df['close'].rolling(20).std()
    df['bb_upper']  = df['ma20'] + 2 * df['std20']
    df['bb_lower']  = df['ma20'] - 2 * df['std20']
    df['ma5']       = df['close'].rolling(5).mean()
    df['ma20_long'] = df['close'].rolling(20).mean()
    df['high20']    = df['high'].rolling(20).max()
    df['low20']     = df['low'].rolling(20).min()
    return df

# ============ 策略信号 ============
def check_buy(df, i, strategy):
    if i < 1: return False
    if strategy == 'bollinger':
        return (df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and
                df['close'].iloc[i]   >  df['bb_upper'].iloc[i])
    elif strategy == 'breakout':
        return (df['close'].iloc[i-1] <= df['high20'].iloc[i-1] and
                df['close'].iloc[i]   >  df['high20'].iloc[i])
    elif strategy == 'ma':
        return (df['ma5'].iloc[i-1]  <= df['ma20_long'].iloc[i-1] and
                df['ma5'].iloc[i]    >  df['ma20_long'].iloc[i])

def check_sell(df, i, entry_price, strategy):
    close = df['close'].iloc[i]
    if close < entry_price * (1 - STOP_LOSS):
        return True, '止损'
    if close > entry_price * (1 + TAKE_PROFIT):
        return True, '止盈'
    if i < 1: return False, None
    if strategy == 'bollinger':
        if (df['close'].iloc[i-1] >= df['bb_lower'].iloc[i-1] and
            close                <  df['bb_lower'].iloc[i]):
            return True, '信号卖出'
    elif strategy == 'breakout':
        if (df['close'].iloc[i-1] >= df['low20'].iloc[i-1] and
            close                <  df['low20'].iloc[i]):
            return True, '信号卖出'
    elif strategy == 'ma':
        if (df['ma5'].iloc[i-1]  >= df['ma20_long'].iloc[i-1] and
            df['ma5'].iloc[i]    <  df['ma20_long'].iloc[i]):
            return True, '信号卖出'
    return False, None

# ============ N=1 回测引擎 ============
def backtest_n1(etf_codes, strategy, initial_cap=INIT_CAP):
    """N=1 全仓轮换回测"""
    # 加载数据
    etf_dfs = {}
    for code in etf_codes:
        df = load_etf(code)
        if df is not None:
            df = calculate_indicators(df)
            etf_dfs[code] = df
    
    if not etf_dfs:
        return None
    
    # 交易日历（并集）
    all_dates = set()
    for df in etf_dfs.values():
        all_dates.update(df['date'].tolist())
    trade_dates = sorted(all_dates)
    
    cash     = initial_cap
    position = None  # {code, shares, entry_price, entry_date}
    trades   = []
    
    for dt in trade_dates:
        # 卖出检查
        if position is not None:
            code = position['code']
            df   = etf_dfs.get(code)
            if df is not None:
                row = df[df['date'] == dt]
                if not row.empty:
                    i = row.index[0]
                    if i >= 25:
                        should_sell, reason = check_sell(df, i, position['entry_price'], strategy)
                        if should_sell:
                            close     = df['close'].iloc[i]
                            sell_value = position['shares'] * close * (1 - FEE_RATE)
                            cash     += sell_value
                            ret = (close / position['entry_price'] - 1) * 100
                            trades.append({
                                'date':   str(dt.date()),
                                'action': reason,
                                'etf':   code,
                                'price':  float(close),
                                'shares': position['shares'],
                                'return': float(ret)
                            })
                            position = None
        
        # 买入检查（空仓）
        if position is None:
            for code in etf_codes:
                df = etf_dfs.get(code)
                if df is None: continue
                row = df[df['date'] == dt]
                if row.empty: continue
                i = row.index[0]
                if i < 25: continue
                if check_buy(df, i, strategy):
                    close  = df['close'].iloc[i]
                    shares = int(cash / close / (1 + FEE_RATE))
                    if shares == 0: continue
                    cost = shares * close * (1 + FEE_RATE)
                    cash -= cost
                    position = {
                        'code':         code,
                        'shares':       shares,
                        'entry_price':  close,
                        'entry_date':   str(dt.date())
                    }
                    trades.append({
                        'date':   str(dt.date()),
                        'action': '买入',
                        'etf':   code,
                        'price':  float(close),
                        'shares': shares,
                        'signal': strategy
                    })
                    break  # N=1
        
    # 最终结算
    final_value = cash
    if position is not None:
        code = position['code']
        df   = etf_dfs.get(code)
        if df is not None:
            final_close = df['close'].iloc[-1]
            final_value += position['shares'] * final_close
    
    completed = [t for t in trades if t['action'] != '买入']
    wins      = [t for t in completed if t.get('return', 0) > 0]
    
    return {
        'final_value':  float(final_value),
        'total_return': float((final_value / initial_cap - 1) * 100),
        'trade_count':  len(completed),
        'win_rate':     float(len(wins)/len(completed)*100 if completed else 0),
        'trades':       trades
    }

# ============ 主程序 ============
if __name__ == '__main__':
    for strategy in ['bollinger', 'breakout', 'ma']:
        print(f"\n{'='*60}")
        print(f"策略: {strategy}")
        print(f"{'='*60}")
        
        for n in [3, 5, 10]:
            etf_pool = get_top_etfs(strategy, n)
            result = backtest_n1(etf_pool, strategy)
            if result is None:
                print(f"  N={n}: 无可用数据")
                continue
            
            print(f"  ETF池大小={n:2d}  最终资产={result['final_value']:>12,.2f}元  "
                  f"收益={result['total_return']:>+7.2f}%  "
                  f"交易={result['trade_count']:3d}次  胜率={result['win_rate']:.1f}%")
    
    print()
