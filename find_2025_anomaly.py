#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找出2025年第一周价格异常的ETF"""
import json, os, sys, glob
from datetime import datetime

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        d = json.load(f)
    return d.get('data', d.get('etfs', []))

def load_history(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not hits:
            hits = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    d = json.load(f)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r['date'], float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        w = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        weeks[w] = cl
                    except:
                        pass
                return sorted(weeks.items())
            except:
                continue
    return None

etfs = load_pool()
print(f'检查195只ETF的2025年第一周数据...\n')

anomalies = []
for etf in etfs:
    code = etf['code']
    s = load_history(code)
    if not s:
        continue
    
    # 找2024最后一周和2025第一周的价格
    price_2024_last = None
    price_2025_first = None
    for w, c in s:
        if w == '2024-W52':
            price_2024_last = c
        if w == '2025-W01':
            price_2025_first = c
    
    if price_2024_last and price_2025_first:
        change = (price_2025_first / price_2024_last - 1) * 100
        if abs(change) > 20:  # 单周涨跌超过20%算异常
            anomalies.append({
                'code': code,
                'name': etf.get('name', ''),
                'price_2024W52': price_2024_last,
                'price_2025W01': price_2025_first,
                'change': change,
            })

print(f'发现 {len(anomalies)} 只ETF在2025年第一周价格异常（涨跌>20%）：\n')
anomalies.sort(key=lambda x: abs(x['change']), reverse=True)
for a in anomalies[:20]:
    print(f'{a["code"]} {a["name"]}: {a["price_2024W52"]:.4f} -> {a["price_2025W01"]:.4f} '
          f'({a["change"]:+.1f}%)')
