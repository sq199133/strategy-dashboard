#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新10只ETF池的数据到最新"""

import json
import os
import urllib.request
import urllib.parse

HIST_DIR = 'D:/QClaw_Trading/data/history'

# 10只ETF池
POOL = ['510050', '510300', '510500', '512100', '159915', 
        '588000', '513500', '513100', '518880', '162411']

def get_market(code):
    if code.startswith('1'):
        return '0'
    return '1'

def fetch_etf_history(code):
    market = get_market(code)
    params = {
        'secid': f'{market}.{code}',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',
        'fqt': '1',
        'beg': '0',
        'end': '20500101',
        'lmt': '1000000'
    }
    
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urllib.parse.urlencode(params)
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        if data.get('rc') != 0 or 'data' not in data or not data['data']:
            return None
        
        klines = data['data']['klines']
        if not klines:
            return None
        
        records = []
        for line in klines:
            parts = line.split(',')
            records.append({
                'date': parts[0],
                'open': float(parts[1]),
                'close': float(parts[2]),
                'high': float(parts[3]),
                'low': float(parts[4]),
                'vol': int(parts[5]),
                'amount': int(parts[6])
            })
        
        return {'code': code, 'name': data['data'].get('name', code), 'records': records}
    except Exception as e:
        print(f'  {code} 获取失败: {e}')
        return None

def main():
    print('更新ETF数据...')
    for code in POOL:
        print(f'  {code}...', end=' ')
        data = fetch_etf_history(code)
        if data:
            path = os.path.join(HIST_DIR, f'{code}.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            last = data['records'][-1]['date']
            print(f'OK, 最新日期 {last}')
        else:
            print('失败')

if __name__ == '__main__':
    main()
