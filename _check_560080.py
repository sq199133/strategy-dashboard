#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, urllib.request, json, re
sys.stdout.reconfigure(encoding='utf-8')
for code in ['560080','159837']:
    secid = ('1.' if code[0] in '56' else '0.') + code
    url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f57,f58,f169&ut=fa5fd1943c7b386f172d6893dbfba10b'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read().decode()
        m = re.search(r'\{.*\}', raw, re.S)
        d = json.loads(m.group()) if m else {}
        dd = d.get('data') or {}
        print(f"{dd.get('f58','?')}({code}) 实时价={dd.get('f43',0)/100:.3f} 涨跌%={dd.get('f169',0)/100:+.2f}")
    except Exception as e:
        print(code, '获取失败', e)
