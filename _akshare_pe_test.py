# -*- coding: utf-8 -*-
"""测试AKShare指数实时PE/PB"""
import akshare as ak, pandas as pd, time

print('=== AKShare指数实时PE/PB测试 ===')
t0 = time.time()
try:
    df = ak.stock_zh_index_spot_em()
    elapsed = time.time() - t0
    print(f'成功! 耗时{elapsed:.1f}s, {len(df)}个指数')
    print(f'字段: {list(df.columns)}')
    print(df[['代码','名称','市盈率-动态','市净率']].head(10).to_string())
    
    # 找宽基指数
    targets = ['000300','000905','000852','399006','000688','000016']
    print('\n--- 宽基指数 ---')
    for t in targets:
        row = df[df['代码'] == t]
        if not row.empty:
            r = row.iloc[0]
            print(f'{r["名称"]}({t}): PE={r["市盈率-动态"]}, PB={r["市净率"]}')
        else:
            print(f'{t}: 未找到')
    
    # 历史PE测试（如果spot可用，测试历史）
    print('\n--- 历史PE测试 ---')
    try:
        hist = ak.index_zh_a_hist(symbol='000300', period='月', start_date='20180101', end_date='20260710', adjust='qfq')
        print(f'指数历史K线: {len(hist)}行, 字段: {list(hist.columns)}')
        print(hist.tail(3))
    except Exception as e:
        print(f'历史K线失败: {e}')
    
    # 测试指数PE历史
    try:
        pe_hist = ak.stock_zh_index_daily(symbol='sh000300')
        print(f'\n指数日线(含PE): {len(pe_hist)}行')
        if not pe_hist.empty:
            print(f'字段: {list(pe_hist.columns)}')
            print(pe_hist.tail(3))
    except Exception as e:
        print(f'日线(含PE)失败: {e}')
    
except Exception as e:
    print(f'失败: {e}')
    import traceback; traceback.print_exc()
