#!/usr/bin/env python3
"""年化收益计算 - 使用虚拟盘配置的ETF池"""
import json, os, glob
import pandas as pd

DATA_DIR    = r"D:\QClaw_Trading\data\history"
INIT_CAP    = 100000
STOP_LOSS   = 0.08
TAKE_PROFIT = 0.15
FEE         = 0.0005

# 虚拟盘配置的ETF池（从virtual_portfolio_state.json读取）
VPOOL = {
    'bollinger': [('159902','中小100ETF华夏'),('161128','标普信息科技LOF'),('163208','全球油气能源LOF')],
    'breakout':  [('159902','中小100ETF华夏'),('161128','标普信息科技LOF'),('160416','石油基金LOF')],
    'ma':        [('160723','嘉实原油LOF'),('159667','工业母机ETF国泰'),('160140','美国REIT精选LOF')],
}

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json','r',encoding='utf-8') as f:
    C = json.load(f)

def load_etf(code):
    for prefix in ['sh','sz']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path,'r',encoding='utf-8') as f:
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

def calc_ind(df):
    df = df.copy()
    df['ma20']      = df['close'].rolling(20).mean()
    df['std20']     = df['close'].rolling(20).std()
    df['bb_upper']  = df['ma20'] + 2*df['std20']
    df['bb_lower']  = df['ma20'] - 2*df['std20']
    df['ma5']       = df['close'].rolling(5).mean()
    df['ma20_long'] = df['close'].rolling(20).mean()
    df['high20']    = df['high'].rolling(20).max()
    df['low20']     = df['low'].rolling(20).min()
    return df

def run_n1(etf_pool, strategy):
    etf_dfs = {}
    for code, _ in etf_pool:
        df = load_etf(code)
        if df is not None:
            etf_dfs[code] = calc_ind(df)

    if not etf_dfs:
        return None

    all_dates = set()
    for df in etf_dfs.values():
        all_dates.update(df['date'].tolist())
    trade_dates = sorted(all_dates)

    cash     = INIT_CAP
    position = None
    trades   = []

    for dt in trade_dates:
        if position is not None:
            code = position['code']
            df   = etf_dfs.get(code)
            if df is not None:
                row = df[df['date'] == dt]
                if not row.empty:
                    i = row.index[0]
                    if i >= 25:
                        close = df['close'].iloc[i]
                        should_sell, reason = False, ''
                        if close < position['entry_price']*(1-STOP_LOSS):
                            should_sell, reason = True, '止损'
                        elif close > position['entry_price']*(1+TAKE_PROFIT):
                            should_sell, reason = True, '止盈'
                        elif strategy=='bollinger' and i>=1:
                            if df['close'].iloc[i-1]>=df['bb_lower'].iloc[i-1] and close<df['bb_lower'].iloc[i]:
                                should_sell, reason = True, '信号卖出'
                        elif strategy=='breakout' and i>=1:
                            if df['close'].iloc[i-1]>=df['low20'].iloc[i-1] and close<df['low20'].iloc[i]:
                                should_sell, reason = True, '信号卖出'
                        elif strategy=='ma' and i>=1:
                            if df['ma5'].iloc[i-1]>=df['ma20_long'].iloc[i-1] and df['ma5'].iloc[i]<df['ma20_long'].iloc[i]:
                                should_sell, reason = True, '信号卖出'
                        if should_sell:
                            cash += position['shares']*close*(1-FEE)
                            ret = (close/position['entry_price']-1)*100
                            trades.append({'date':str(dt.date()),'action':reason,'etf':code,'ret':float(ret)})
                            position = None

        if position is None:
            for code, _ in etf_pool:
                df = etf_dfs.get(code)
                if df is None: continue
                row = df[df['date']==dt]
                if row.empty: continue
                i = row.index[0]
                if i < 25: continue
                close = df['close'].iloc[i]
                buy = False
                if strategy=='bollinger' and i>=1:
                    buy = df['close'].iloc[i-1]<=df['bb_upper'].iloc[i-1] and close>df['bb_upper'].iloc[i]
                elif strategy=='breakout' and i>=1:
                    buy = df['close'].iloc[i-1]<=df['high20'].iloc[i-1] and close>df['high20'].iloc[i]
                elif strategy=='ma' and i>=1:
                    buy = df['ma5'].iloc[i-1]<=df['ma20_long'].iloc[i-1] and df['ma5'].iloc[i]>df['ma20_long'].iloc[i]
                if buy:
                    shares = int(cash/close/(1+FEE))
                    if shares == 0: continue
                    cash -= shares*close*(1+FEE)
                    position = {'code':code,'shares':shares,'entry_price':close}
                    trades.append({'date':str(dt.date()),'action':'买入','etf':code})
                    break

    final_value = cash
    holding_return = 0
    if position is not None:
        code = position['code']
        df   = etf_dfs.get(code)
        if df is not None:
            final_value += position['shares']*df['close'].iloc[-1]
            holding_return = (df['close'].iloc[-1]/position['entry_price']-1)*100

    first_date = trade_dates[0]
    last_date  = trade_dates[-1]
    years = (last_date - first_date).days / 365.25

    completed = [t for t in trades if t['action'] not in ('买入',)]
    wins      = [t for t in completed if t.get('ret',0) > 0]
    total_ret = (final_value/INIT_CAP-1)*100
    annual_ret = ((final_value/INIT_CAP)**(1/years)-1)*100 if years>0 else 0

    return {
        'final':        float(final_value),
        'total_ret':    float(total_ret),
        'annual_ret':   float(annual_ret),
        'trade_count':  len(completed),
        'win_rate':     float(len(wins)/len(completed)*100) if completed else 0,
        'years':        float(years),
        'start_date':   str(first_date.date()),
        'end_date':     str(last_date.date()),
        'etf_pool':     etf_pool,
        'holding_ret':  float(holding_return),
        'trades':       trades,
    }

if __name__ == '__main__':
    print("="*72)
    print(f"{'策略':<12} {'回测区间':^28} {'总收益':>10} {'年化':>8} {'交易':>5} {'胜率':>6}")
    print("="*72)
    for strat, label in [('bollinger','布林带突破'),('breakout','趋势突破'),('ma','均线交叉')]:
        r = run_n1(VPOOL[strat], strat)
        if r:
            print(f"{label:<12} {r['start_date']} ~ {r['end_date']}  {r['total_ret']:>+9.1f}%  {r['annual_ret']:>+6.1f}%  {r['trade_count']:4d}次  {r['win_rate']:5.1f}%")
            print(f"             池: {', '.join(n for _,n in r['etf_pool'])}")
            if r['holding_ret'] != 0:
                print(f"             当前持仓浮盈: {r['holding_ret']:+.1f}%")
            # 打印前5笔和后5笔交易
            if r['trades']:
                buys = [t for t in r['trades'] if t['action']=='买入']
                if buys:
                    print(f"             买入次数: {len(buys)}, 最近3笔:")
                    for t in buys[-3:]:
                        print(f"               {t['date']} {t['etf']}")
            print()
