# -*- coding: utf-8 -*-
"""探测腾讯指数PE/PB数据接口"""
import sys, json
sys.path.insert(0, r'D:\QClaw_Trading')
import qclaw_stock_data as qsd

print('=== VALUATION_SOURCES ===')
print(qsd.VALUATION_SOURCES)

print('\n=== INDEX_SOURCES ===')
print(qsd.INDEX_SOURCES)

print('\n=== SourceRouter ===')
print(dir(qsd.SourceRouter))

# 测试获取指数实时PE
print('\n=== 测试获取指数PE ===')
fetcher = qsd.DataFetcher()

# 指数代码格式测试
test_codes = [
    'sh000300',  # 沪深300
    'sh000905',  # 中证500
    'sz399006',  # 创业板指
    'sh000016',  # 上证50
    'sh000688',  # 科创50
    'sh000852',  # 中证1000
]

for code in test_codes:
    print(f'\n--- {code} ---')
    try:
        # 测试实时行情
        r = fetcher.get_quote(code)
        if r:
            print(f'  实时行情: {list(r.keys())[:10]}')
            print(f'  PE: {r.get("peTTM", "N/A")}')
            print(f'  PB: {r.get("pbMRQ", "N/A")}')
        else:
            print('  无行情')
    except Exception as e:
        print(f'  异常: {e}')

# 测试指数历史PE
print('\n=== 测试指数历史PE ===')
try:
    hist = fetcher.get_index_history_pe('sh000300', start='2025-01-01', end='2026-07-10')
    print(f'历史PE: {len(hist)}行')
    if hist is not None and not hist.empty:
        print(hist.head(5))
except Exception as e:
    print(f'get_index_history_pe 失败: {e}')

# 直接请求腾讯接口
print('\n=== 直接请求腾讯PE接口 ===')
try:
    import requests
    # 腾讯指数PE接口
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=sh000300,day,2025-01-01,2026-07-10,1000,qfq'
    r = requests.get(url, timeout=10)
    print(f'腾讯qfq接口: status={r.status_code}, len={len(r.text)}')
    print(r.text[:500])
except Exception as e:
    print(f'腾讯接口失败: {e}')

# 腾讯另一PE接口
try:
    import requests
    # 指数估值接口
    url2 = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rank/getRankListByValue?dev=1&page=0&pageSize=20&type=pe&order=asc&market=sz'
    r2 = requests.get(url2, timeout=10)
    print(f'\n腾讯估值排名接口: status={r2.status_code}, len={len(r2.text)}')
    print(r2.text[:500])
except Exception as e:
    print(f'腾讯排名接口失败: {e}')

# 尝试新浪指数PE
print('\n=== 新浪指数PE ===')
try:
    import requests
    # 新浪财经指数PE（如果有的话）
    url3 = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page=1&num=5&sort=pe&asc=0&node=hs_a&symbol=&_s_r_a=page'
    r3 = requests.get(url3, timeout=10)
    print(f'新浪: status={r3.status_code}, text={r3.text[:300]}')
except Exception as e:
    print(f'新浪PE失败: {e}')
