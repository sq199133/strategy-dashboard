#!/usr/bin/env python3
"""
多持仓并行回测 — 对比 N=1 / N=3 / N=5 只ETF同时持仓的收益
规则：
  - 每只ETF独立判断买卖信号
  - 新买入时分配资金 = 当前现金 / (最大持仓数 - 当前持仓数)
  - 卖出后现金回笼，可供后续买入复用
  - 最大持仓数 max_positions = N
"""

import json
import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from copy import deepcopy

# ============ 配置 ============
DATA_DIR   = r"D:\QClaw_Trading\data\history"
INIT_CAP   = 100000       # 初始资金（单策略）
STOP_LOSS  = 0.08         # 止损 8%
TAKE_PROFIT = 0.15       # 止盈 15%
FEE_RATE   = 0.0005       # 手续费（双边）

# 候选 ETF 池（用之前 multi_strategy_candidates.json 中表现最好的前N只）
# 这里用布林带突破策略的TOP ETF
TOP_ETF_CODES = [
    "159902",   # 中小100ETF华夏  布林带 +1155.6%
    "161128",   # 标普信息科技LOF  布林带 +484.8%
    "163208",   # 全球油气能源LOF 布林带 +431.6%
    "159667",   # 工业母机ETF国泰  均线交叉 +98.4%
    "160140",   # 美国REIT精选LOF 均线交叉 +89.7%
]


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
    df['ma20']       = df['close'].rolling(20).mean()
    df['std20']      = df['close'].rolling(20).std()
    df['bb_upper']   = df['ma20'] + 2 * df['std20']
    df['bb_lower']   = df['ma20'] - 2 * df['std20']
    df['ma5']        = df['close'].rolling(5).mean()
    df['ma20_long']  = df['close'].rolling(20).mean()
    df['high20']     = df['high'].rolling(20).max()
    df['low20']      = df['low'].rolling(20).min()
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.abs(df['close'] - df['close'].shift(1))
    )
    df['atr'] = df['tr'].rolling(14).mean()
    return df


# ============ 策略判断（无状态，只判断信号）============
class BollingerStrategy:
    name = "布林带突破"
    @staticmethod
    def check_buy(df, i):
        if i < 1: return False
        return (df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and
                df['close'].iloc[i]   >  df['bb_upper'].iloc[i])
    @staticmethod
    def check_sell(df, i, entry_price):
        close = df['close'].iloc[i]
        if close < entry_price * (1 - STOP_LOSS):
            return True, '止损'
        if close > entry_price * (1 + TAKE_PROFIT):
            return True, '止盈'
        if i < 1: return False, None
        if (df['close'].iloc[i-1] >= df['bb_lower'].iloc[i-1] and
            close                <  df['bb_lower'].iloc[i]):
            return True, '信号卖出'
        return False, None


class BreakoutStrategy:
    name = "趋势突破"
    @staticmethod
    def check_buy(df, i):
        if i < 1: return False
        return (df['close'].iloc[i-1] <= df['high20'].iloc[i-1] and
                df['close'].iloc[i]   >  df['high20'].iloc[i])
    @staticmethod
    def check_sell(df, i, entry_price):
        close = df['close'].iloc[i]
        if close < entry_price * (1 - STOP_LOSS):
            return True, '止损'
        if close > entry_price * (1 + TAKE_PROFIT):
            return True, '止盈'
        if i < 1: return False, None
        if (df['close'].iloc[i-1] >= df['low20'].iloc[i-1] and
            close                <  df['low20'].iloc[i]):
            return True, '信号卖出'
        return False, None


class MAStrategy:
    name = "均线交叉"
    @staticmethod
    def check_buy(df, i):
        if i < 1: return False
        return (df['ma5'].iloc[i-1]  <= df['ma20_long'].iloc[i-1] and
                df['ma5'].iloc[i]    >  df['ma20_long'].iloc[i])
    @staticmethod
    def check_sell(df, i, entry_price):
        close = df['close'].iloc[i]
        if close < entry_price * (1 - STOP_LOSS):
            return True, '止损'
        if close > entry_price * (1 + TAKE_PROFIT):
            return True, '止盈'
        if i < 1: return False, None
        if (df['ma5'].iloc[i-1]  >= df['ma20_long'].iloc[i-1] and
            df['ma5'].iloc[i]    <  df['ma20_long'].iloc[i]):
            return True, '信号卖出'
        return False, None


STRATEGY_MAP = {
    'bollinger': BollingerStrategy,
    'breakout': BreakoutStrategy,
    'ma':        MAStrategy,
}


# ============ 多持仓回测引擎 ============
def run_multi_position(etf_codes, strategy_type, max_positions=1,
                       initial_capital=INIT_CAP):
    """
    对一组ETF运行多持仓并行回测。
    每只ETF独立判断买卖，最大同时持有 max_positions 只。
    """
    strategy = STRATEGY_MAP[strategy_type]

    # 1) 加载所有ETF数据，取日期交集
    dfs = {}
    for code in etf_codes:
        df = load_etf(code)
        if df is None:
            print(f"  [跳过] {code} 数据不存在")
            continue
        df = calculate_indicators(df)
        dfs[code] = df

    if not dfs:
        return None

    # 用所有ETF日期的并集，按日期对齐
    all_dates = set()
    for df in dfs.values():
        all_dates.update(df['date'].tolist())
    all_dates = sorted(all_dates)
    # 过滤：只保留每个ETF都有的日期（交集更严谨）
    # 这里用并集 + forward fill 方式处理

    # 2) 初始化持仓状态
    # positions: {etf_code: {'shares': int, 'entry_price': float, 'entry_date': str}}
    positions   = {}
    cash        = initial_capital
    trades      = []
    equity_curve = []

    # 把每个ETF的 df 重新索引到统一日期（向前填充）
    # 简化：用每个ETF自己的日期序列，但保证在同一天只处理一次买卖
    # 更严谨的做法：统一到交易日历
    # 这里简化：遍历所有ETF的所有交易日（union），对每个ETF独立判断

    # 构建统一交易日历（所有ETF日期的并集，排序）
    union_dates = sorted(all_dates)

    for dt in union_dates:
        # 当天每只已持仓ETF先检查卖出
        to_close = []
        for code in list(positions.keys()):
            pos  = positions[code]
            df    = dfs.get(code)
            if df is None: continue
            # 找到当天在 df 中的 row
            row = df[df['date'] == dt]
            if row.empty: continue
            i = row.index[0]
            if i < 25: continue

            should_sell, reason = strategy.check_sell(df, i, pos['entry_price'])
            if should_sell:
                close_price = df['close'].iloc[i]
                sell_value  = pos['shares'] * close_price * (1 - FEE_RATE)
                cash       += sell_value
                ret = (close_price / pos['entry_price'] - 1) * 100
                trades.append({
                    'date':   str(dt.date()),
                    'action': reason,
                    'etf':    code,
                    'price':  float(close_price),
                    'shares': pos['shares'],
                    'return': float(ret)
                })
                to_close.append(code)

        for code in to_close:
            del positions[code]

        # 当天检查未持仓的ETF是否有买入信号（不超过最大持仓数）
        if len(positions) < max_positions:
            for code in etf_codes:
                if code in positions: continue
                df = dfs.get(code)
                if df is None: continue
                row = df[df['date'] == dt]
                if row.empty: continue
                i = row.index[0]
                if i < 25: continue

                if strategy.check_buy(df, i):
                    # 分配资金
                    alloc      = cash / (max_positions - len(positions))
                    close_price = df['close'].iloc[i]
                    shares      = int(alloc / close_price / (1 + FEE_RATE))
                    if shares == 0: continue
                    cost = shares * close_price * (1 + FEE_RATE)
                    cash -= cost
                    positions[code] = {
                        'shares':      shares,
                        'entry_price':  close_price,
                        'entry_date':   str(dt.date())
                    }
                    trades.append({
                        'date':   str(dt.date()),
                        'action': '买入',
                        'etf':    code,
                        'price':  float(close_price),
                        'shares': shares,
                        'signal': strategy.name
                    })

        # 记录当天权益
        total_position_value = 0
        for code, pos in positions.items():
            df = dfs.get(code)
            if df is None: continue
            row = df[df['date'] == dt]
            if row.empty:
                # 用昨收盘价近似
                last_idx = df[df['date'] < dt]['close'].index
                if len(last_idx) > 0:
                    total_position_value += pos['shares'] * df['close'].iloc[last_idx[-1]]
            else:
                total_position_value += pos['shares'] * df['close'].iloc[row.index[0]]
        equity_curve.append({
            'date':  str(dt.date()),
            'value': float(cash + total_position_value)
        })

    # 最终按最新价格结算
    final_value = cash
    for code, pos in positions.items():
        df = dfs.get(code)
        if df is None: continue
        final_close = df['close'].iloc[-1]
        final_value += pos['shares'] * final_close

    return {
        'final_value':   float(final_value),
        'total_return':  float((final_value / initial_capital - 1) * 100),
        'trades':        trades,
        'equity_curve':  equity_curve,
        'n_positions':   max_positions,
    }


# ============ 主程序 ============
if __name__ == "__main__":
    etf_pool = TOP_ETF_CODES[:5]   # 用前5只
    strategy_type = 'bollinger'      # 统一用布林带突破做对比

    print(f"回测池（前{len(etf_pool)}只ETF）: {etf_pool}")
    print(f"策略: {STRATEGY_MAP[strategy_type].name}")
    print(f"初始资金: {INIT_CAP:,}元  止损:{STOP_LOSS*100:.0f}%  止盈:{TAKE_PROFIT*100:.0f}%\n")

    for n in [1, 3, 5]:
        print(f"{'='*60}")
        print(f"  最大持仓数 N = {n}")
        print(f"{'='*60}")
        result = run_multi_position(
            etf_pool[:n],   # 只取前n只ETF
            strategy_type,
            max_positions=n,
            initial_capital=INIT_CAP
        )
        if result is None:
            print("  [失败] 无可用数据\n")
            continue

        completed = [t for t in result['trades'] if t['action'] != '买入']
        wins      = [t for t in completed if t.get('return', 0) > 0]
        win_rate   = len(wins)/len(completed)*100 if completed else 0

        print(f"  最终资产: {result['final_value']:,.2f} 元")
        print(f"  总收益率: {result['total_return']:+.2f}%")
        print(f"  总交易次数: {len(completed)}")
        print(f"  胜率: {win_rate:.1f}%")
        if completed:
            rets = [t['return'] for t in completed]
            print(f"  平均收益: {np.mean(rets):.2f}%")
            print(f"  最大单次盈利: {max(rets):.2f}%")
            print(f"  最大单次亏损: {min(rets):.2f}%")
        print()
