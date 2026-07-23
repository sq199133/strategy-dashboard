#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载指数历史数据"""
import urllib.request, json, time, os

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'

def fetch_index_kline(code):
    # 指数前缀规则：
    #   399xxx = 深证 -> sz
    #   000300 = 上证指数 -> sh（虽然代码是000开头，但是上证指数）
    if code.startswith('399'):
        prefix = 'sz'
    else:
        prefix = 'sh'  # 000300 等上证指数
    sym = f'{prefix}{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,500,qfq'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
        d = raw.get('data', {}).get(sym, {})
        klines = d.get('qfqday', []) or d.get('day', [])
        if not klines:
            print(f'  {sym}: 无数据')
            return False
        out = []
        for k in klines:
            try:
                vol = int(float(k[5])) if k[5] else 0
            except:
                vol = 0
            out.append({'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
                        'high': float(k[3]), 'low': float(k[4]), 'vol': vol})
        fname = f'{prefix}{code}.json'
        fpath = os.path.join(HISTORY_DIR, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f'  保存 {fname}: {len(out)} 条')
        return True
    except Exception as e:
        print(f'  {sym}: 失败 {e}')
        return False

print('下载指数数据...')
for code in ['000300']:
    fetch_index_kline(code)
    time.sleep(1)
print('完成')
