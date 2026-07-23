#!/usr/bin/env python3
"""布林带突破 - 不同池大小的N=1回测对比"""
import json, os, glob
import pandas as pd

DATA_DIR    = r"D:\QClaw_Trading\data\history"
INIT_CAP    = 100000
STOP_LOSS   = 0.08
TAKE_PROFIT = 0.15
FEE         = 0.0005

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json','r',encoding='utf-8') as f:
    C = json.load(f)

key = '布林带突破'
items = sorted(C['all_results'], key=lambda x: x[key]['total_return'], reverse=True)
print('布林带突破 TOP15 ETF:')
for i, it in enumerate(items[:15]):
    print(f'  {i+1:2d}. {it["code"]} {it["name"]:<16s} 总收益:{it[key]["total_return"]:>+7.1f}%  交易:{it[key]["trade_count"]:3d}次  胜率:{it[key]["win_rate"]:.1f}%')

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
    return df

def run_n1(etf_pool):
    etf_dfs = {}
    for code in etf_pool:
        df = load_etf(code)
        if df is not None:
            etf_dfs[code] = calc_ind(df)
    if not etf_dfs:
        return None
    all_dates = set()
    for df in etf_dfs.values():
        all_dates.update(df['date'].tolist())
    trade_dates = sorted(all_dates)
    cash = INIT_CAP
    position = None
    trades = []
    for dt in trade_dates:
        if position is not None:
            code = position['code']
            df = etf_dfs.get(code)
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
                        elif i>=1:
                            if df['close'].iloc[i-1]>=df['bb_lower'].iloc[i-1] and close<df['bb_lower'].iloc[i]:
                                should_sell, reason = True, '信号卖出'
                        if should_sell:
                            cash += position['shares']*close*(1-FEE)
                            ret = (close/position['entry_price']-1)*100
                            trades.append({'date':str(dt.date()),'action':reason,'etf':code,'ret':float(ret)})
                            position = None
        if position is None:
            for code in etf_pool:
                df = etf_dfs.get(code)
                if df is None: continue
                row = df[df['date']==dt]
                if row.empty: continue
                i = row.index[0]
                if i < 25: continue
                close = df['close'].iloc[i]
                if i>=1 and df['close'].iloc[i-1]<=df['bb_upper'].iloc[i-1] and close>df['bb_upper'].iloc[i]:
                    shares = int(cash/close/(1+FEE))
                    if shares == 0: continue
                    cash -= shares*close*(1+FEE)
                    position = {'code':code,'shares':shares,'entry_price':close}
                    trades.append({'date':str(dt.date()),'action':'买入','etf':code})
                    break
    final_value = cash
    if position is not None:
        code = position['code']
        df = etf_dfs.get(code)
        if df is not None:
            final_value += position['shares']*df['close'].iloc[-1]
    first_date = trade_dates[0]
    last_date  = trade_dates[-1]
    years = (last_date - first_date).days / 365.25
    completed = [t for t in trades if t['action'] not in ('买入',)]
    wins = [t for t in completed if t.get('ret',0) > 0]
    total_ret = (final_value/INIT_CAP-1)*100
    annual_ret = ((final_value/INIT_CAP)**(1/years)-1)*100 if years>0 else 0
    return {'final':float(final_value),'total_ret':float(total_ret),'annual_ret':float(annual_ret),'trade_count':len(completed),'win_rate':float(len(wins)/len(completed)*100) if completed else 0,'years':float(years),'start_date':str(first_date.date()),'end_date':str(last_date.date()),'trades':trades}

print()
print('='*72)
print(f"{'池大小':>6} {'最终资产':>14} {'总收益':>10} {'年化收益':>8} {'交易次数':>6} {'胜率':>6} {'起始日期':>12}")
print('='*72)
for n in [3, 5, 8, 10, 15, 20]:
    pool = [it['code'] for it in items[:n]]
    r = run_n1(pool)
    if r:
        print(f'  TOP{n:2d}  {r["final"]:>14,.0f}  {r["total_ret"]:>+9.1f}%  {r["annual_ret"]:>+7.1f}%  {r["trade_count"]:5d}次  {r["win_rate"]:5.1f}%  {r["start_date"]} ~ {r["end_date"]}')
