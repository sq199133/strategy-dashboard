#!/usr/bin/env python3
"""
ETF虚拟盘 - 批量回测筛选 & 初始化
对标的池中所有有历史数据的ETF跑三策略回测，输出综合评分
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

# ============ 配置 ============
DATA_DIR = r"D:\QClaw_Trading\data\history"
POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
INITIAL_CAPITAL = 50000  # 虚拟盘初始资金
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15

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
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                return df
    return None

def calculate_indicators(df):
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['ma20'] + 2 * df['std20']
    df['bb_lower'] = df['ma20'] - 2 * df['std20']
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20_long'] = df['close'].rolling(20).mean()
    df['high20'] = df['high'].rolling(20).max()
    df['low20'] = df['low'].rolling(20).min()
    return df

# ============ 策略 ============
class BollingerStrategy:
    name = "布林带突破"
    @staticmethod
    def check_buy(df, i, pos): return pos > 0 or \
        not (df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and df['close'].iloc[i] > df['bb_upper'].iloc[i])
    @staticmethod
    def check_sell(df, i, pos, entry):
        if pos == 0: return False, None
        c = df['close'].iloc[i]
        if c < entry * (1 - STOP_LOSS): return True, '止损'
        if c > entry * (1 + TAKE_PROFIT): return True, '止盈'
        if df['close'].iloc[i-1] >= df['bb_lower'].iloc[i-1] and c < df['bb_lower'].iloc[i]: return True, '信号卖出'
        return False, None

class BreakoutStrategy:
    name = "趋势突破"
    @staticmethod
    def check_buy(df, i, pos): return pos > 0 or \
        not (df['close'].iloc[i-1] <= df['high20'].iloc[i-1] and df['close'].iloc[i] > df['high20'].iloc[i])
    @staticmethod
    def check_sell(df, i, pos, entry):
        if pos == 0: return False, None
        c = df['close'].iloc[i]
        if c < entry * (1 - STOP_LOSS): return True, '止损'
        if c > entry * (1 + TAKE_PROFIT): return True, '止盈'
        if df['close'].iloc[i-1] >= df['low20'].iloc[i-1] and c < df['low20'].iloc[i]: return True, '信号卖出'
        return False, None

class MAStrategy:
    name = "均线交叉"
    @staticmethod
    def check_buy(df, i, pos): return pos > 0 or \
        not (df['ma5'].iloc[i-1] <= df['ma20_long'].iloc[i-1] and df['ma5'].iloc[i] > df['ma20_long'].iloc[i])
    @staticmethod
    def check_sell(df, i, pos, entry):
        if pos == 0: return False, None
        c = df['close'].iloc[i]
        if c < entry * (1 - STOP_LOSS): return True, '止损'
        if c > entry * (1 + TAKE_PROFIT): return True, '止盈'
        if df['ma5'].iloc[i-1] >= df['ma20_long'].iloc[i-1] and df['ma5'].iloc[i] < df['ma20_long'].iloc[i]: return True, '信号卖出'
        return False, None

# ============ 单ETF单策略回测 ============
def backtest(df, strategy_cls):
    if df is None or len(df) < 30: return None
    df = calculate_indicators(df.copy())
    s = strategy_cls()
    cash, shares, entry = INITIAL_CAPITAL, 0, 0.0
    trades, completed = [], []
    
    for i in range(25, len(df)):
        close = df['close'].iloc[i]
        if shares == 0:
            if not s.check_buy(df, i, 0):
                if (df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and close > df['bb_upper'].iloc[i]) or \
                   (df['close'].iloc[i-1] <= df['high20'].iloc[i-1] and close > df['high20'].iloc[i]) or \
                   (df['ma5'].iloc[i-1] <= df['ma20_long'].iloc[i-1] and df['ma5'].iloc[i] > df['ma20_long'].iloc[i]):
                    shares = int(cash / close * 0.995)
                    entry = close
                    cash -= shares * close
                    trades.append({'action': '买入', 'price': float(close), 'date': str(df['date'].iloc[i].date()), 'signal': s.name})
        else:
            should, reason = s.check_sell(df, i, shares, entry)
            if should:
                ret = (close / entry - 1) * 100
                cash += shares * close
                trades.append({'action': reason, 'price': float(close), 'return': float(ret), 'date': str(df['date'].iloc[i].date())})
                completed.append(ret)
                shares, entry = 0, 0.0
    
    final = cash + shares * df['close'].iloc[-1]
    total_ret = (final / INITIAL_CAPITAL - 1) * 100
    wins = [r for r in completed if r > 0]
    
    return {
        'total_return': total_ret,
        'final_value': float(final),
        'trade_count': len(completed),
        'win_rate': len(wins) / len(completed) * 100 if completed else 0,
        'avg_return': np.mean(completed) if completed else 0,
        'max_win': max(completed) if completed else 0,
        'max_loss': min(completed) if completed else 0,
        'trades': trades
    }

# ============ 主程序 ============
if __name__ == "__main__":
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    strategies = [BollingerStrategy, BreakoutStrategy, MAStrategy]
    results = []
    
    print("开始批量回测...")
    for item in pool['data']:
        code = item['code']
        name = item.get('name', code)
        category = item.get('category', '未知')
        scale = item.get('scale')
        
        df = load_etf(code)
        if df is None: continue
        
        best_strategy = None
        best_return = -999
        
        for strat_cls in strategies:
            r = backtest(df, strat_cls)
            if r:
                r['etf_code'] = code
                r['etf_name'] = name
                r['category'] = category
                r['scale'] = scale
                r['strategy'] = strat_cls.name
                results.append(r)
                if r['total_return'] > best_return:
                    best_return = r['total_return']
                    best_strategy = strat_cls.name
        
        print(f"  {code} {name}: 最佳策略={best_strategy} 收益={best_return:+.1f}%")
    
    # 按总收益排序，筛选优质标的
    results.sort(key=lambda x: x['total_return'], reverse=True)
    
    # 筛选：交易次数>=3，胜率>=50%，收益为正
    filtered = [r for r in results if r['trade_count'] >= 3 and r['win_rate'] >= 50 and r['total_return'] > 0]
    
    # 选不同类别代表：每个类别取最优
    selected = {}
    for r in filtered:
        cat = r['category'] or '其他'
        if cat not in selected or r['total_return'] > selected[cat]['total_return']:
            # 控制总数量不超过8只
            if len(selected) < 8:
                selected[cat] = r
    
    print(f"\n批量回测完成，共{len(results)}条结果，过滤后{len(filtered)}条")
    print(f"精选{len(selected)}只ETF进入虚拟盘：")
    for cat, r in selected.items():
        print(f"  [{cat}] {r['etf_code']} {r['etf_name']} | {r['strategy']} | 收益{r['total_return']:+.1f}% | 胜率{r['win_rate']:.0f}%")
    
    # 输出精选标的
    output = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pool_total': pool['total'],
        'backtested': len(results),
        'filtered': len(filtered),
        'selected_etfs': list(selected.values()),
        'all_results': results[:50]  # 只保留前50条
    }
    
    with open(r"D:\QClaw_Trading\data\virtual_portfolio_candidates.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n候选结果已保存到 virtual_portfolio_candidates.json")
