#!/usr/bin/env python3
"""DEBUG: 检查nav_list和关键变量"""
import json, os
import pandas as pd
import numpy as np

DATA_DIR = r"D:\QClaw_Trading\data\history"
INIT_CAP = 100000; STOP_LOSS = 0.08; TAKE_PROFIT = 0.15; FEE = 0.0005

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json','r',encoding='utf-8') as f:
    C = json.load(f)

key = '布林带突破'
items = sorted(C['all_results'], key=lambda x: x[key]['total_return'], reverse=True)
TOP3 = [it['code'] for it in items[:3]]
print("TOP3:", TOP3)

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
                return df
    return None

def calc_ind(df):
    df = df.copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['ma20'] + 2*df['std20']
    df['bb_lower'] = df['ma20'] - 2*df['std20']
    return df

etf_dfs = {}
for code in TOP3:
    df = load_etf(code)
    if df is not None:
        etf_dfs[code] = calc_ind(df)

all_dates = set()
for df in etf_dfs.values():
    all_dates.update(df['date'].tolist())
trade_dates = sorted(all_dates)
print(f"总交易日: {len(trade_dates)}")

# 建立 date->close 映射
close_map = {}
for code, df in etf_dfs.items():
    for _, row in df.iterrows():
        close_map.setdefault(row['date'], {})[code] = row['close']

# 建立 bb 信号映射（前一根K的信号）
prev_bb_upper = {}
prev_bb_lower = {}
prev_close    = {}
for code, df in etf_dfs.items():
    for j in range(1, len(df)):
        dt = df['date'].iloc[j]
        prev_bb_upper[dt] = df['bb_upper'].iloc[j-1]
        prev_bb_lower[dt] = df['bb_lower'].iloc[j-1]
        prev_close[dt]    = df['close'].iloc[j-1]

cash     = INIT_CAP
position = None
nav_list = [INIT_CAP]
trade_log = []

for dt in trade_dates:
    closes = close_map.get(dt, {})
    pbu = prev_bb_upper.get(dt)
    pbl = prev_bb_lower.get(dt)
    pc  = prev_close.get(dt)

    if position is not None and position['code'] in closes:
        close = closes[position['code']]
        sl = close < position['entry_price']*(1-STOP_LOSS)
        tp = close > position['entry_price']*(1+TAKE_PROFIT)
        sig = (pbl is not None and pc is not None and pc >= pbl and close < pbl)
        if sl or tp or sig:
            action = '止损' if sl else ('止盈' if tp else '信号卖出')
            cash += position['shares']*close*(1-FEE)
            ret = (close/position['entry_price']-1)*100
            trade_log.append({'date':str(dt.date()),'action':action,'etf':position['code'],'ret':ret,'nav':cash})
            position = None

    if position is None:
        for code in TOP3:
            if code not in closes: continue
            if dt not in prev_bb_upper: continue
            if pbu is None or pc is None: continue
            close = closes[code]
            if pc <= pbu and close > pbu:
                shares = int(cash/close/(1+FEE))
                if shares == 0: continue
                cash -= shares*close*(1+FEE)
                position = {'code':code,'shares':shares,'entry_price':close}
                trade_log.append({'date':str(dt.date()),'action':'买入','etf':code,'ret':0,'nav':cash+shares*close})
                break

    cur_val = cash
    if position is not None and position['code'] in closes:
        cur_val += position['shares'] * closes[position['code']]
    nav_list.append(cur_val)

dr = np.diff(nav_list) / np.array(nav_list[:-1])
dr = dr[~np.isnan(dr) & ~np.isinf(dr)]
annual_ret = float(np.mean(dr) * 252)
annual_vol = float(np.std(dr, ddof=1) * np.sqrt(252))
sharpe = (annual_ret - 0.03) / annual_vol if annual_vol > 0 else 0
nav_arr = np.array(nav_list)
cummax = np.maximum.accumulate(nav_arr)
drawdown = (nav_arr - cummax) / cummax
max_dd = float(np.min(drawdown)) * 100

print(f"\n===== 结果 =====")
print(f"nav_list[0] = {nav_list[0]:,.0f}")
print(f"nav_list[-1] = {nav_list[-1]:,.0f}")
print(f"len(nav_list) = {len(nav_list)}")
print(f"len(dr) = {len(dr)}")
print(f"交易日数覆盖: {len(nav_list)-1}天")
print(f"年化收益率(arithmetic): {annual_ret*100:+.2f}%")
print(f"年化波动率: {annual_vol*100:+.2f}%")
print(f"夏普比率: {sharpe:+.2f}")
print(f"最大回撤: {max_dd:+.2f}%")
print(f"交易次数: {len(trade_log)}")
buys = [t for t in trade_log if t['action']=='买入']
sells = [t for t in trade_log if t['action']!='买入']
print(f"买入: {len(buys)}次, 卖出: {len(sells)}次")
print(f"\n前10笔交易:")
for t in trade_log[:10]:
    print(f"  {t['date']} {t['action']} {t['etf']} ret={t['ret']:+.1f}% nav={t.get('nav',0):,.0f}")
print(f"\n后5笔交易:")
for t in trade_log[-5:]:
    print(f"  {t['date']} {t['action']} {t['etf']} ret={t['ret']:+.1f}%")
