#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update local history files for all ETFs in the pool.
Run this weekly (after Friday close) to keep backtest data in sync with scan data.
"""

import json, os, sys, time, urllib.request
from datetime import datetime

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

def get_prefix(code):
    return 'sh' if code.startswith('6') else 'sz'

def fetch_kline(code):
    prefix = get_prefix(code)
    for alt in [prefix, 'sz' if prefix == 'sh' else 'sh']:
        sym = f'{alt}{code}'
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,300,qfq'
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://gu.qq.com/'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read().decode('utf-8'))
            d = raw.get('data', {}).get(sym, {})
            klines = d.get('qfqday', []) or d.get('day', [])
            if klines:
                return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), int(float(k[5]))) for k in klines]
        except Exception as e:
            print(f'  {code} error: {e}')
            time.sleep(0.5)
        if alt != prefix:
            break
    return []

def save_history(code, daily):
    records = [{'date': ds, 'open': o, 'close': c, 'high': h, 'low': l, 'vol': v} for ds, o, c, h, l, v in daily]
    for prefix in ['sh', 'sz']:
        path = os.path.join(HISTORY_DIR, f'{prefix}{code}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    return len(records)

def main():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    etfs = data.get('data', data.get('etfs', []))
    
    print(f'Updating {len(etfs)} ETFs...')
    ok = 0
    fail = 0
    
    for i, etf in enumerate(etfs):
        code = etf['code']
        print(f'[{i+1}/{len(etfs)}] {code}  ', end='', flush=True)
        daily = fetch_kline(code)
        if daily:
            n = save_history(code, daily)
            print(f'OK ({n} days)')
            ok += 1
        else:
            print('FAIL')
            fail += 1
        time.sleep(0.3)  # Rate limit
    
    print(f'\nDone. OK={ok} FAIL={fail}')

if __name__ == '__main__':
    main()
