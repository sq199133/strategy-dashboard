# -*- coding: utf-8 -*-
"""获取实时行情数据"""
import requests, json, time

HEAD = {'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com'}

codes = ['sh000300','sh000905','sh000852','sz399006','sh000688',
         'sh510300','sh510500','sh512100','sz159915','sh588080']
url = 'https://qt.gtimg.cn/q=' + ','.join(codes)
r = requests.get(url, headers=HEAD, timeout=8)
r.encoding = 'gbk'

results = {}
for line in r.text.strip().split('\n'):
    if '=' not in line: continue
    raw = line.split('=',1)[1].strip('";')
    parts = raw.split('~')
    if len(parts) > 4:
        name = parts[1]
        price = parts[3]
        chg = parts[31] if len(parts)>31 else '0'
        chg_pct = parts[32] if len(parts)>32 else '0'
        high = parts[33] if len(parts)>33 else '0'
        low = parts[34] if len(parts)>34 else '0'
        open_p = parts[5] if len(parts)>5 else '0'
        vol = parts[6] if len(parts)>6 else '0'
        results[name] = {
            'price': price, 'chg': chg, 'chg_pct': chg_pct,
            'high': high, 'low': low, 'open': open_p, 'vol': vol
        }

print('REAL_TIME_DATA=' + json.dumps(results, ensure_ascii=False))
