# -*- coding: utf-8 -*-
"""探测中证/东方财富/申万指数PE历史"""
import requests, json, pandas as pd

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
           'Referer': 'https://www.csindex.com.cn/'}

# 测试1: 中证指数官网API
print('=== CSI 指数PE历史 ===')
try:
    # 尝试新格式
    url = 'https://www.csindex.com.cn/csindex_home/perf/index-perf/query/index-perf?indexCode=000300&startDate=2018-01-01&endDate=2026-07-10&type=D'
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = 'utf-8'
    print(f'status={r.status_code}, content-type={r.headers.get("content-type")}')
    print(f'text前500: {r.text[:500]}')
    
    # 尝试另一种格式
    url2 = 'https://www.csindex.com.cn/csindex_home/index-detail/000300/ircalc?startDate=2018-01-01&endDate=2026-07-10'
    r2 = requests.get(url2, headers=HEADERS, timeout=15)
    print(f'\nCSI v2: status={r2.status_code}, text={r2.text[:500]}')
except Exception as e:
    print(f'CSI失败: {e}')

# 测试2: 中证指数估值数据
print('\n=== CSI 指数估值 ===')
try:
    url = 'https://www.csindex.com.cn/csindex_home/index-detail/000300/valuation?startDate=2018-01-01&endDate=2026-07-10'
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = 'utf-8'
    print(f'status={r.status_code}, text={r.text[:500]}')
except Exception as e:
    print(f'CSI估值失败: {e}')

# 测试3: 申万宏源指数PE
print('\n=== 申万宏源指数PE ===')
try:
    # 申万行业指数PE历史
    url = 'https://www.swsindex.com/idx0120.aspx?swindexcode=801010'
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f'申万: status={r.status_code}, len={len(r.text)}')
except Exception as e:
    print(f'申万失败: {e}')

# 测试4: 腾讯全量指数行情（含PE）
print('\n=== 腾讯全量指数行情(含PE) ===')
try:
    # 腾讯全量指数
    url = 'https://qt.gtimg.cn/q=s_sh000001,s_sh000300,s_sh000905,s_sz399006,s_sh000688,s_sz399005'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com'}, timeout=10)
    r.encoding = 'gbk'
    for line in r.text.strip().split('\n'):
        if line.strip() and '~' in line:
            parts = line.split('~')
            name = parts[1] if len(parts) > 1 else '?'
            price = parts[3] if len(parts) > 3 else '?'
            pe = parts[39] if len(parts) > 39 else '?'
            pb = parts[46] if len(parts) > 46 else '?'
            print(f'{name}: price={price} PE={pe} PB={pb}')
except Exception as e:
    print(f'腾讯全量失败: {e}')

# 测试5: 腾讯历史(含PE, 用不同接口)
print('\n=== 腾讯历史K线(含PE) ===')
try:
    # 腾讯财经指数历史(含PE)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh000300,d,,,,5000,qfq'
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f'腾讯月K: status={r.status_code}, text={r.text[:600]}')
except Exception as e:
    print(f'腾讯月K失败: {e}')

# 测试6: 尝试东方财富指数历史(含PE)
print('\n=== 东方财富指数月K(含PE) ===')
try:
    # 月线
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000300&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60&klt=102&fqt=1&beg=20180101&end=20260710'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.eastmoney.com'}, timeout=10)
    data = r.json()
    if 'data' in data and data['data']:
        klines = data['data'].get('klines', [])
        fields = data['data'].get('fields2', [])
        print(f'月K条数: {len(klines)}, 字段: {fields}')
        if klines:
            print(f'最新: {klines[-1]}')
    else:
        print(f'失败: {r.text[:200]}')
except Exception as e:
    print(f'EM月K失败: {e}')

# 测试7: 新浪指数实时(含PE)
print('\n=== 新浪指数实时(含PE) ===')
try:
    url = 'https://hq.sinajs.cn/list=s_sh000300,s_sh000905,s_sz399006,s_sh000688'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'}, timeout=10)
    r.encoding = 'gbk'
    print(f'新浪指数实时: {r.text[:600]}')
except Exception as e:
    print(f'新浪失败: {e}')
