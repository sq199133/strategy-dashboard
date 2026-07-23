#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接从东方财富API获取ETF今日/近期行情"""

import requests
import json
import time

# ETF代码映射
ETF_LIST = [
    ('588000', '科创50'),
    ('159915', '创业板指'),
    ('510300', '沪深300'),
    ('510500', '中证500'),
    ('512100', '中证1000'),
    ('510050', '上证50'),
    ('513500', '标普500'),
    ('513100', '纳指ETF'),
    ('518880', '黄金ETF'),
    ('162411', '华宝油气'),
]

def fetch_ef_data(code):
    """从东方财富获取近期K线数据"""
    # 判断交易所
    if code.startswith('1') or code.startswith('2'):
        mkt = '0'  # 深圳
    else:
        mkt = '1'  # 上海
    
    url = f'http://push2his.eastmoney.com/api/qt/stock/kline/get'
    params = {
        'secid': f'{mkt}.{code}',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',   # 日K
        'fqt': '1',     # 前复权
        'lmt': '10',    # 最近10天
        'end': '20500101',
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            records = []
            for kline in klines:
                parts = kline.split(',')
                records.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5]),
                })
            return records
        else:
            return None
    except Exception as e:
        return None

# 获取所有ETF数据
print('=== 从东方财富API获取数据 ===\n')
results = {}
for code, name in ETF_LIST:
    records = fetch_ef_data(code)
    if records:
        latest = records[-1]
        prev = records[-2] if len(records) > 1 else latest
        pchg = (latest['close'] - prev['close']) / prev['close'] * 100
        results[code] = {
            'name': name,
            'date': latest['date'],
            'open': latest['open'],
            'close': latest['close'],
            'high': latest['high'],
            'low': latest['low'],
            'pchg': pchg,
        }
        print(f'  {code} {name}: {latest["date"]} close={latest["close"]:.3f} ({pchg:+.2f}%)')
        time.sleep(0.3)
    else:
        print(f'  {code} {name}: 获取失败')

# KC50持仓盈亏
if '588000' in results:
    kc = results['588000']
    buy_price = 2.01
    buy_date = '2026-06-24'
    buy_shares = 20000
    
    pnl_pct = (kc['close'] - buy_price) / buy_price * 100
    pnl_amount = buy_shares * (kc['close'] - buy_price)
    cost = buy_shares * buy_price
    value = buy_shares * kc['close']
    
    print(f'\n=== KC50 持仓盈亏 ===\n')
    print(f'买入日:   {buy_date}  买入价: {buy_price:.3f}')
    print(f'当前日:   {kc["date"]}  当前价: {kc["close"]:.3f}')
    print(f'浮动盈亏: {pnl_pct:+.2f}%')
    print(f'浮动盈利: {pnl_amount:+,.0f} 元')
    print(f'持仓市值: {value:,.0f} 元 (成本 {cost:,.0f} 元)')

# 保存结果供后续使用
with open(r'D:\QClaw_Trading\RSRS\ef_today.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\n数据已保存到 ef_today.json')
