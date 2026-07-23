# -*- coding: utf-8 -*-
"""多源探测指数PE/PB"""
import requests, pandas as pd, time, json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 测试1: 腾讯指数实时数据（含PE）
print('=== 腾讯 qt.gtimg.cn ===')
test_idx = ['sh000300','sh000905','sz399006','sh000688','sh000016']
codes_str = ','.join([f'{c}10' for c in test_idx])  # 加10后缀拿实时快照
try:
    url = f'https://qt.gtimg.cn/q={codes_str}'
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.encoding = 'gbk'
    lines = r.text.strip().split('\n')
    for line in lines:
        if line.strip():
            parts = line.split('~')
            if len(parts) > 40:
                name = parts[1]
                price = parts[3]
                pe = parts[39] if len(parts) > 39 else 'N/A'
                pb = parts[46] if len(parts) > 46 else 'N/A'
                print(f'{name}: price={price} PE={pe} PB={pb}')
except Exception as e:
    print(f'失败: {e}')

# 测试2: 中证指数官网
print('\n=== 中证指数官网 CSI ===')
try:
    # 沪深300 PE历史
    url = 'https://www.csindex.com.cn/csindex_home/perf/index-perf/query/index-perf?indexCode=000300&startDate=2018-01-01&endDate=2026-07-10&type=D'
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f'status={r.status_code}, len={len(r.text)}')
    data = r.json()
    if data and 'data' in data:
        records = data['data']
        print(f'记录数: {len(records)}')
        if records:
            print(f'字段: {list(records[0].keys())}')
            print(records[:2])
    else:
        print(r.text[:300])
except Exception as e:
    print(f'CSI失败: {e}')

# 测试3: 另一个CSI接口
print('\n=== CSI PE历史 (v2) ===')
try:
    url = 'https://www.csindex.com.cn/csindex_home/index-detail/000300/ircalc?startDate=2018-01-01&endDate=2026-07-10&type=D'
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f'status={r.status_code}, len={len(r.text)}')
    print(r.text[:500])
except Exception as e:
    print(f'CSI v2失败: {e}')

# 测试4: 东方财富指数PE
print('\n=== 东方财富指数PE ===')
try:
    # 东方财富指数 PE历史
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000300&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=1&beg=20180101&end=20260710'
    r = requests.get(url, headers=HEADERS, timeout=10)
    data = r.json()
    if 'data' in data and data['data']:
        klines = data['data']['klines']
        print(f'东方财富日K: {len(klines)}条')
        if klines:
            print(f'字段: date,open,close,high,low,vol,amount,...')
            print(f'示例: {klines[0]}')
    else:
        print(f'失败: {r.text[:200]}')
except Exception as e:
    print(f'EM PE失败: {e}')

# 测试5: 东方财富指数实时PE
print('\n=== 东方财富指数实时 ===')
try:
    url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.000300&fields=f57,f58,f59,f162,f163,f164,f167,f168'
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f'EM实时: {r.text[:300]}')
except Exception as e:
    print(f'EM实时失败: {e}')

# 测试6: 新浪指数PE排名（可能有批量PE）
print('\n=== 新浪指数PE ===')
try:
    # 尝试新浪指数PE排行
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page=1&num=10&sort=pe&asc=0&node=hs_50&symbol=&_s_r_a=page'
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f'新浪50: {r.text[:300]}')
except Exception as e:
    print(f'新浪PE失败: {e}')

# 测试7: 腾讯指数估值
print('\n=== 腾讯指数估值 ===')
try:
    # 腾讯财经指数估值数据
    url = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/indexapp/getIndexInfo?indexCode=sh000300&startDate=20180101&endDate=20260710&type=D&dev=1'
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f'腾讯指数: status={r.status_code}, text={r.text[:400]}')
except Exception as e:
    print(f'腾讯指数估值失败: {e}')
