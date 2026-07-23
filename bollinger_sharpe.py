#!/usr/bin/env python3
"""布林带TOP3 完整风险指标（修复nav归零bug）"""
import json, os, glob
import pandas as pd
import numpy as np

DATA_DIR = r"D:\QClaw_Trading\data\history"
RF = 0.03
INIT_CAP = 100000; STOP_LOSS = 0.08; TAKE_PROFIT = 0.15; FEE = 0.0005

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json','r',encoding='utf-8') as f:
    C = json.load(f)

key = '布林带突破'
items = sorted(C['all_results'], key=lambda x: x[key]['total_return'], reverse=True)
TOP3 = [it['code'] for it in items[:3]]

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
    df['ma20']     = df['close'].rolling(20).mean()
    df['std20']    = df['close'].rolling(20).std()
    df['bb_upper'] = df['ma20'] + 2*df['std20']
    df['bb_lower'] = df['ma20'] - 2*df['std20']
    return df

etf_dfs = {}
for code in TOP3:
    df = load_etf(code)
    if df is not None:
        etf_dfs[code] = calc_ind(df)
        print(f"{code} {items[[it['code'] for it in items].index(code)]['name']}: {len(df)}条, {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")

all_dates = set()
for df in etf_dfs.values():
    all_dates.update(df['date'].tolist())
trade_dates = sorted(all_dates)
print(f"\n合并交易日历: {len(trade_dates)}天, {trade_dates[0].strftime('%Y-%m-%d')} ~ {trade_dates[-1].strftime('%Y-%m-%d')}")

cash = INIT_CAP; position = None; nav_list = []; trades = []

for dt in trade_dates:
    # 找到当日各ETF的收盘价和指标（仅当日有数据的ETF才处理）
    today_data = {}
    for code, df in etf_dfs.items():
        row = df[df['date']==dt]
        if not row.empty:
            idx = row.index[0]
            today_data[code] = {'close': df['close'].iloc[idx], 'bb_upper': df['bb_upper'].iloc[idx],
                                'bb_lower': df['bb_lower'].iloc[idx], 'i': idx}

    # 持仓的当前收盘价（有数据时）
    pos_close = None
    if position:
        if position['code'] in today_data:
            pos_close = today_data[position['code']]['close']

    # 记录nav（持仓则用昨收/今收；无数据则用cash carry-forward）
    if position and pos_close is not None:
        nav_list.append(cash + position['shares'] * pos_close)
    elif position:
        # 持仓但当日无数据 → nav沿用昨日（不计入收益序列）
        nav_list.append(None)
    else:
        nav_list.append(cash)

    # 卖出检查（仅当日有持仓数据才处理）
    if position and position['code'] in today_data:
        td = today_data[position['code']]
        close = td['close']
        i = td['i']
        if i >= 25:
            sell, reason = False, ''
            if close < position['entry_price']*(1-STOP_LOSS):
                sell, reason = True, '止损'
            elif close > position['entry_price']*(1+TAKE_PROFIT):
                sell, reason = True, '止盈'
            elif i>=2 and etf_dfs[position['code']].iloc[i-1]['close'] >= td['bb_lower'] and close < td['bb_lower']:
                sell, reason = True, '信号卖出'
            if sell:
                cash += position['shares']*close*(1-FEE)
                trades.append({'ret':(close/position['entry_price']-1)*100,'action':reason,'date':str(dt.date())})
                position = None

    # 买入检查（仅当日有数据才处理）
    if not position:
        for code in TOP3:
            if code not in today_data: continue
            td = today_data[code]
            i = td['i']
            if i < 26: continue
            close = td['close']
            prev_row = etf_dfs[code].iloc[i-1]
            if prev_row['close'] <= td['bb_upper'] and close > td['bb_upper']:
                shares = int(cash/close/(1+FEE))
                if shares == 0: continue
                cash -= shares*close*(1+FEE)
                position = {'code':code,'shares':shares,'entry_price':close}
                trades.append({'ret':0,'action':'买入','date':str(dt.date())})
                break

# 最终结算
nav_valid = [v for v in nav_list if v is not None]
final_val = nav_valid[-1] if nav_valid else cash
years     = (trade_dates[-1]-trade_dates[0]).days/365.25

# 风险指标（过滤连续None导致的断裂点）
valid_pairs = [(v, nav_list[i+1]) for i,v in enumerate(nav_list[:-1])
               if v is not None and nav_list[i+1] is not None]
print(f'  nav有效天数={len(valid_pairs)}/{len(nav_list)}，缺失天数={nav_list.count(None)}')

dr_arr = np.array([(b-a)/a for a,b in valid_pairs])
annual_ret  = float(np.mean(dr_arr)*252)
annual_vol  = float(np.std(dr_arr,ddof=1)*np.sqrt(252))
sharpe      = (annual_ret-RF)/annual_vol if annual_vol>0 else 0
nav_arr     = np.array(nav_valid)
cummax      = np.maximum.accumulate(nav_arr)
max_dd      = float(np.min((nav_arr-cummax)/cummax))*100
geo_annual  = ((nav_arr[-1]/nav_arr[0])**(1/years)-1)*100 if years>0 and nav_arr[-1]>0 else 0
closed      = [t for t in trades if t['action']!='买入']
wins        = [t for t in closed if t['ret']>0]

print(f"\n===== 布林带TOP3 风险指标 =====")
print(f"  最终净值     : {nav_arr[-1]:>14,.0f} 元")
print(f"  几何年化收益  : {geo_annual:>+8.2f}%")
print(f"  算数年化收益  : {annual_ret*100:>+8.2f}%")
print(f"  年化波动率    : {annual_vol*100:>+8.2f}%")
print(f"  夏普比率      : {sharpe:>+8.2f}  (无风险利率3%)")
print(f"  最大回撤      : {max_dd:>+8.2f}%")
print(f"  Calmar比率    : {geo_annual/abs(max_dd):>+8.2f}" if max_dd != 0 else "  Calmar比率   : N/A")
print(f"  完成交易次数  : {len(closed):>6d} 次")
print(f"  胜率          : {len(wins)/len(closed)*100:>6.1f}%")
print(f"  回测区间      : {trade_dates[0].strftime('%Y-%m-%d')} ~ {trade_dates[-1].strftime('%Y-%m-%d')} ({years:.1f}年)")
print()
print("TOP3 ETF:")
for i, it in enumerate(items[:3]):
    print(f"  {i+1}. {it['code']} {it['name']}")
