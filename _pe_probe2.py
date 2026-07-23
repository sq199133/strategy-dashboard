# -*- coding: utf-8 -*-
"""详细探测PE数据源"""
import requests, json, pandas as pd

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 测试1: 腾讯 qt.gtimg.cn - 详细字段
print('=== 腾讯qt字段详细 ===')
try:
    codes = ['sh00030010', 'sh00090510', 'sz39900610', 'sh00068810', 'sh51050010']
    url = f'https://qt.gtimg.cn/q={",".join(codes)}'
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.encoding = 'gbk'
    for line in r.text.strip().split('\n'):
        if line.strip():
            parts = line.split('~')
            print(f'总字段数: {len(parts)}')
            for i, p in enumerate(parts):
                if p and p not in ['', 'undefined']:
                    print(f'  [{i}] = {p}')
            print()
except Exception as e:
    print(f'失败: {e}')

# 测试2: 东方财富指数实时详情（多个field）
print('\n=== 东方财富指数实时详情 ===')
test_ids = ['1.000300', '1.000905', '0.399006', '1.000688', '1.000016']
for sid in test_ids:
    try:
        fields = 'f57,f58,f59,f162,f163,f164,f167,f168,f169,f170,f171,f172,f173,f174'
        url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={sid}&fields={fields}'
        req = requests.get(url, headers=HEADERS, timeout=8)
        data = req.json()
        if data.get('data'):
            d = data['data']
            print(f"{d.get('f58', sid)}: PE={d.get('f162')}, PB={d.get('f163')}, 股息率={d.get('f164')}, 52W高={d.get('f173')}, 52W低={d.get('f174')}")
        else:
            print(f'{sid}: 无数据')
    except Exception as e:
        print(f'{sid}失败: {e}')

# 测试3: 东方财富指数历史（含PE）
print('\n=== 东方财富指数历史（含PE）===')
try:
    # 东方财富指数历史K线(带PE/PB) - 用日线
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000300&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20250101&end=20260710'
    r = requests.get(url, headers=HEADERS, timeout=10)
    data = r.json()
    if 'data' in data and data['data']:
        klines = data['data'].get('klines', [])
        fields = data['data'].get('fields2', [])
        print(f'东方财富指数日K: {len(klines)}条')
        print(f'字段: {fields}')
        if klines:
            print(f'示例: {klines[-1]}')
    else:
        print(f'失败: {r.text[:200]}')
except Exception as e:
    print(f'失败: {e}')

# 测试4: 新浪指数历史(含PE字段)
print('\n=== 新浪指数含PE历史 ===')
try:
    # 新浪财经指数历史K线
    url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=5&datalen=3000'
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f'新浪指数: status={r.status_code}, text={r.text[:400]}')
except Exception as e:
    print(f'新浪指数失败: {e}')

# 测试5: 尝试AKShare stock_zh_index_daily (指数日线含PE)
print('\n=== AKShare指数日线(含PE) ===')
try:
    import akshare as ak
    # 注意: 这个是按日期获取指数数据
    df = ak.stock_zh_index_daily(symbol='sh000300')
    print(f'指数日线: {len(df)}行, 字段: {list(df.columns)}')
    if not df.empty:
        print(df.tail(3))
except Exception as e:
    print(f'失败: {e}')
