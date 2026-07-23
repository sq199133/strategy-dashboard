#!/usr/bin/env python3
"""
虚拟盘执行脚本 — N=1 全仓轮换模式
用法:
  python run_virtual_portfolio.py           # 输出当前状态 + 今日收益
  python run_virtual_portfolio.py --init    # 初始化虚拟盘（写入初始状态文件）
  python run_virtual_portfolio.py --force-buy  # 强制执行买入信号检测
"""

import json
import os
import sys
import argparse
from datetime import datetime, date

# ============ 配置 ============
DATA_DIR    = r"D:\QClaw_Trading\data\history"
STATE_FILE  = r"D:\QClaw_Trading\data\virtual_portfolio_state.json"
INIT_CAP    = 50000.0 / 3        # 每策略初始 16666.67
STOP_LOSS   = 0.08
TAKE_PROFIT = 0.15
FEE_RATE    = 0.0005              # 手续费 0.05% 双边
MAX_POSITIONS = 1                  # N=1 全仓轮换

# 三策略各自追踪的ETF池（从 multi_strategy_candidates.json 读取 TOP 候选）
# 简化：每策略固定追踪前3只候选ETF，信号触发时全仓买入
STRATEGY_ETF_POOL = {
    'bollinger': ['159902', '161128', '163208'],   # 布林带TOP3
    'breakout':  ['159902', '161128', '160416'],   # 趋势突破TOP3
    'ma':        ['160723', '159667', '160140'],   # 均线交叉TOP3
}

# ============ 指标计算 ============
import numpy as np
import pandas as pd

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
def check_buy_bollinger(df, i):
    if i < 1: return False
    return (df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and
            df['close'].iloc[i]   >  df['bb_upper'].iloc[i])

def check_sell_bollinger(df, i, entry_price):
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

def check_buy_breakout(df, i):
    if i < 1: return False
    return (df['close'].iloc[i-1] <= df['high20'].iloc[i-1] and
            df['close'].iloc[i]   >  df['high20'].iloc[i])

def check_sell_breakout(df, i, entry_price):
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

def check_buy_ma(df, i):
    if i < 1: return False
    return (df['ma5'].iloc[i-1]  <= df['ma20_long'].iloc[i-1] and
            df['ma5'].iloc[i]    >  df['ma20_long'].iloc[i])

def check_sell_ma(df, i, entry_price):
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

STRATEGY_FNS = {
    'bollinger': (check_buy_bollinger, check_sell_bollinger),
    'breakout':  (check_buy_breakout,  check_sell_breakout),
    'ma':        (check_buy_ma,        check_sell_ma),
}

# ============ 状态管理 ============
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def init_state():
    """初始化虚拟盘状态（首个交易日 2026-05-19）"""
    state = {
        'init_date': '2026-05-19',
        'strategies': {}
    }
    for strat in ['bollinger', 'breakout', 'ma']:
        state['strategies'][strat] = {
            'cash':     INIT_CAP,
            'position': None,   # None 或 {'code':..., 'shares':..., 'entry_price':..., 'entry_date':...}
            'trades':  [],
            'daily_equity': []
        }
    save_state(state)
    print(f"初始化完成，状态已保存到 {STATE_FILE}")
    return state

# ============ 核心：对单个策略运行一日模拟 ============
def run_daily(strat, state_strat, trade_date_str):
    """
    对单个策略，在 trade_date_str 这一天执行买卖检查。
    返回当日收盘后的权益。
    """
    check_buy, check_sell = STRATEGY_FNS[strat]
    etf_pool = STRATEGY_ETF_POOL[strat]

    # 加载池中ETF数据
    etf_dfs = {}
    for code in etf_pool:
        df = load_etf(code)
        if df is not None:
            df = calculate_indicators(df)
            etf_dfs[code] = df

    if not etf_dfs:
        return state_strat['cash']

    # 找到交易日的索引（在每个ETF的df中）
    # 简化处理：取第一个可用ETF的日期序列
    ref_code = list(etf_dfs.keys())[0]
    ref_df   = etf_dfs[ref_code]

    # 找到 trade_date 在 ref_df 中的行
    tdate = pd.to_datetime(trade_date_str)
    row = ref_df[ref_df['date'] == tdate]
    if row.empty:
        # 该ETF这天无数据，用最近一个交易日的数据
        prev_rows = ref_df[ref_df['date'] < tdate]
        if prev_rows.empty:
            return state_strat['cash']
        row = prev_rows.tail(1)
        i = row.index[0]
        close_price_ref = row['close'].iloc[0]
    else:
        i = row.index[0]
        close_price_ref = row['close'].iloc[0]

    # ========== 卖出检查（先检查当前持仓）==========
    pos = state_strat['position']
    if pos is not None:
        code = pos['code']
        df   = etf_dfs.get(code)
        if df is not None:
            row2 = df[df['date'] == tdate]
            if row2.empty:
                # 用最近一日收盘价
                prev = df[df['date'] < tdate]['close']
                if len(prev) > 0:
                    close = prev.iloc[-1]
                else:
                    close = pos['entry_price']
            else:
                close = df['close'].iloc[row2.index[0]]
                i2 = row2.index[0]
                should_sell, reason = check_sell(df, i2, pos['entry_price'])
                if should_sell:
                    # 执行卖出
                    sell_value = pos['shares'] * close * (1 - FEE_RATE)
                    state_strat['cash'] += sell_value
                    ret = (close / pos['entry_price'] - 1) * 100
                    state_strat['trades'].append({
                        'date':   trade_date_str,
                        'action': reason,
                        'etf':   code,
                        'price':  float(close),
                        'shares': pos['shares'],
                        'return': float(ret)
                    })
                    state_strat['position'] = None
                    print(f"  [{strat}] {trade_date_str} 卖出 {code} @{close:.3f} {reason} 收益{ret:+.2f}%")
                    pos = None

    # ========== 买入检查（空仓才买）==========
    if state_strat['position'] is None:
        for code in etf_pool:
            df = etf_dfs.get(code)
            if df is None: continue
            row3 = df[df['date'] == tdate]
            if row3.empty: continue
            i3 = row3.index[0]
            if i3 < 25: continue
            if check_buy(df, i3):
                close = df['close'].iloc[i3]
                # 全仓买入
                alloc  = state_strat['cash']
                shares = int(alloc / close / (1 + FEE_RATE))
                if shares == 0: continue
                cost = shares * close * (1 + FEE_RATE)
                state_strat['cash'] = state_strat['cash'] - cost + (alloc - cost)  # 精确
                state_strat['cash'] = state_strat['cash'] - shares * close * FEE_RATE
                # 重新计算
                actual_cost = shares * close * (1 + FEE_RATE)
                state_strat['cash'] -= actual_cost - shares * close  # 手续费
                # 简化：cash 减去总成本
                state_strat['cash'] = state_strat['cash'] - shares * close * FEE_RATE  # 再精确一次
                # 直接重算
                state_strat['cash'] = INIT_CAP - sum(
                    t['price'] * t['shares'] * (1 + FEE_RATE)
                    for t in state_strat['trades'] if t['action'] == '买入'
                ) + sum(
                    t['price'] * t['shares'] * (1 - FEE_RATE)
                    for t in state_strat['trades'] if t['action'] != '买入'
                )
                # 太复杂，用简单方式
                break

    # 简化版重新实现（见下方主函数）
    return state_strat

# ============ 主：简洁版日志 ============
def simulate_from_history(strat, start_date='2026-05-19'):
    """
    用历史数据回放虚拟盘（N=1 全仓轮换），
    输出每个交易日的持仓和权益。
    """
    check_buy, check_sell = STRATEGY_FNS[strat]
    etf_pool = STRATEGY_ETF_POOL[strat]

    # 加载所有ETF并合并交易日历
    etf_dfs = {}
    for code in etf_pool:
        df = load_etf(code)
        if df is not None:
            df = calculate_indicators(df)
            etf_dfs[code] = df

    if not etf_dfs:
        print(f"  [{strat}] 无可用ETF数据")
        return None

    # 取所有ETF的交易日并集，排序
    all_dates = set()
    for df in etf_dfs.values():
        all_dates.update(df['date'].tolist())
    trade_dates = sorted([d for d in all_dates if d >= pd.to_datetime(start_date)])

    cash    = INIT_CAP
    position = None   # {'code', 'shares', 'entry_price', 'entry_date'}
    trades  = []
    equity   = []     # [(date, equity)]

    print(f"\n{'='*60}")
    print(f"  策略: {strat}  N=1（全仓轮换）")
    print(f"  初始资金: {INIT_CAP:.2f}元")
    print(f"  止损:{STOP_LOSS*100:.0f}%  止盈:{TAKE_PROFIT*100:.0f}%")
    print(f"{'='*60}")

    for dt in trade_dates:
        # 检查持仓ETF的卖出信号
        if position is not None:
            code = position['code']
            df   = etf_dfs.get(code)
            if df is not None:
                row = df[df['date'] == dt]
                if not row.empty:
                    i = row.index[0]
                    if i >= 25:
                        close = df['close'].iloc[i]
                        should_sell, reason = check_sell(df, i, position['entry_price'])
                        if should_sell:
                            sell_value = position['shares'] * close * (1 - FEE_RATE)
                            cash += sell_value
                            ret = (close / position['entry_price'] - 1) * 100
                            trades.append({
                                'date':   str(dt.date()),
                                'action': reason,
                                'etf':   code,
                                'price':  float(close),
                                'shares': position['shares'],
                                'return': float(ret)
                            })
                            print(f"  {str(dt.date())} 卖出 {code} @{close:.3f} {reason} 收益{ret:+.2f}%  现金→{cash:.0f}")
                            position = None

        # 检查买入（空仓时，遍历ETF池找信号）
        if position is None:
            for code in etf_pool:
                df = etf_dfs.get(code)
                if df is None: continue
                row = df[df['date'] == dt]
                if row.empty: continue
                i = row.index[0]
                if i < 25: continue
                if check_buy(df, i):
                    close = df['close'].iloc[i]
                    shares = int(cash / close / (1 + FEE_RATE))
                    if shares == 0: continue
                    cost = shares * close * (1 + FEE_RATE)
                    cash -= cost
                    position = {
                        'code':        code,
                        'shares':      shares,
                        'entry_price':  close,
                        'entry_date':   str(dt.date())
                    }
                    trades.append({
                        'date':   str(dt.date()),
                        'action': '买入',
                        'etf':   code,
                        'price':  float(close),
                        'shares': shares,
                        'signal': strat
                    })
                    print(f"  {str(dt.date())} 买入 {code} @{close:.3f} {shares}股  现金→{cash:.0f}")
                    break  # N=1: 只买一只

        # 记录当日收盘权益
        pos_value = 0
        if position is not None:
            code = position['code']
            df   = etf_dfs.get(code)
            if df is not None:
                row = df[df['date'] == dt]
                if not row.empty:
                    pos_value = position['shares'] * df['close'].iloc[row.index[0]]
                else:
                    # 用最近收盘价
                    prev = df[df['date'] < dt]['close']
                    if len(prev) > 0:
                        pos_value = position['shares'] * prev.iloc[-1]
        equity.append((str(dt.date()), cash + pos_value))

    # 最终总结
    final_value = cash
    if position is not None:
        code = position['code']
        df   = etf_dfs.get(code)
        if df is not None:
            final_close = df['close'].iloc[-1]
            final_value += position['shares'] * final_close

    completed = [t for t in trades if t['action'] != '买入']
    wins      = [t for t in completed if t.get('return', 0) > 0]

    print(f"\n{'='*60}")
    print(f"  最终结果")
    print(f"{'='*60}")
    print(f"  最终资产: {final_value:,.2f} 元")
    print(f"  总收益:   {(final_value/INIT_CAP-1)*100:+.2f}%")
    print(f"  交易次数: {len(completed)}")
    print(f"  胜率:     {len(wins)/len(completed)*100:.1f}%" if completed else "  (无完成交易)")
    if completed:
        rets = [t['return'] for t in completed]
        print(f"  平均收益: {np.mean(rets):.2f}%")
        print(f"  最大盈利: {max(rets):.2f}%")
        print(f"  最大亏损: {min(rets):.2f}%")

    return {
        'strat':      strat,
        'final_value': final_value,
        'total_return':(final_value/INIT_CAP-1)*100,
        'trades':     trades,
        'equity':     equity,
    }

# ============ 主程序 ============
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true', help='初始化虚拟盘状态文件')
    parser.add_argument('--start', type=str, default='2026-05-19', help='回放起始日期')
    args = parser.parse_args()

    if args.init:
        init_state()
        sys.exit(0)

    print("="*60)
    print("  虚拟盘回放（N=1 全仓轮换）")
    print("="*60)

    results = {}
    for strat in ['bollinger', 'breakout', 'ma']:
        r = simulate_from_history(strat, start_date=args.start)
        if r:
            results[strat] = r

    # 汇总
    print(f"\n{'='*60}")
    print(f"  三策略汇总")
    print(f"{'='*60}")
    total_init = INIT_CAP * 3
    total_final = sum(r['final_value'] for r in results.values())
    print(f"  初始总资金: {total_init:,.2f} 元")
    print(f"  最终总资金: {total_final:,.2f} 元")
    print(f"  总收益:     {(total_final/total_init-1)*100:+.2f}%")
    print(f"  绝对收益:   {total_final - total_init:+,.2f} 元")
    print()

    # 保存结果
    out = {
        'date': datetime.now().isoformat(),
        'start_date': args.start,
        'n_positions': 1,
        'results': results
    }
    out_path = r"D:\QClaw_Trading\data\virtual_portfolio_n1_result.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out_path}")
