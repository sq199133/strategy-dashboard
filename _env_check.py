#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, urllib.request, json, re
sys.stdout.reconfigure(encoding='utf-8')

indices = [
    ('sh000001', '上证指数'),
    ('sh000300', '沪深300'),
    ('sz399006', '创业板指'),
    ('sh000905', '中证500'),
    ('sz399001', '深证成指'),
]
etfs = [
    ('sh560080', '中药ETF'),
    ('sz159837', '生物科技ETF'),
    ('sz159928', '消费ETF'),
    ('sz512010', '医药ETF'),
]

def get_weekly(secid):
    url = f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1&fields2=f51,f53&klt=102&fqt=0&beg=20260601&end=20260717'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read().decode()
        d = json.loads(raw)
        kl = d.get('data',{}).get('klines',[])
        if not kl: return None
        rows = [ (k.split(',')[0], float(k.split(',')[1])) for k in kl ]
        # 取最近5周
        last5 = rows[-5:]
        return last5
    except Exception as e:
        return f'ERR:{e}'

print("="*70)
print("  本周(2026-07-17)大环境与板块表现")
print("="*70)
print(f"{'名称':<12}{'07-10':>9}{'07-17':>9}{'周涨跌':>9}")
for secid, name in indices + etfs:
    res = get_weekly(secid)
    if isinstance(res, str):
        print(f"{name:<12} {res}")
        continue
    if not res:
        print(f"{name:<12} 无数据")
        continue
    # 找07-10和07-17
    d = {r[0]: r[1] for r in res}
    p10 = d.get('2026-07-10')
    p17 = d.get('2026-07-17')
    if p10 and p17:
        chg = (p17/p10 - 1)*100
        print(f"{name:<12}{p10:>9.3f}{p17:>9.3f}{chg:>+8.2f}%")
    else:
        print(f"{name:<12} 07-10={p10} 07-17={p17}")
