# -*- coding: utf-8 -*-
import akshare as ak
import time

# 尝试多种ETF历史数据接口
tests = [
    ('fund_etf_hist_sina', lambda: ak.fund_etf_hist_sina(symbol='sh510300')),
    ('fund_etf_hist_ths', lambda: ak.fund_etf_hist_ths(symbol='510300', indicator='历史行情')),
]

for name, fn in tests:
    try:
        print(f'\n=== {name} ===')
        result = fn()
        print(f'success! rows: {len(result)}, cols: {list(result.columns)}')
        print(result.head(3))
    except Exception as e:
        print(f'{name} error: {type(e).__name__}: {e}')
    time.sleep(2)

# 测试获取全市场ETF代码列表
print('\n=== fund_etf_spot_em (ETF列表) ===')
try:
    df = ak.fund_etf_spot_em()
    print(f'success! rows: {len(df)}')
    print('relevant cols:', [c for c in df.columns if '代码' in c or '名称' in c or 'PE' in c or 'PB' in c])
    # 查找有PE/PB的ETF
    pe_cols = [c for c in df.columns if '市盈率' in c or 'PE' in c.upper() or 'PE' in c]
    print('PE cols:', pe_cols)
    if pe_cols:
        valid_pe = df[df[pe_cols[0]].notna()]
        print(f'ETFs with PE: {len(valid_pe)}')
except Exception as e:
    print(f'error: {e}')
