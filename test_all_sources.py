#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test ALL available data sources for ETF historical data"""

import sys
import os
import json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

TEST_CODES = ['510880', '159915', '513500']
START_DATE = '20100101'
END_DATE = datetime.now().strftime('%Y%m%d')

results = {}

# ============================
# 1. AKShare
# ============================
print("=" * 60)
print("1. AKShare (fund_etf_hist_em)")
print("=" * 60)
try:
    import akshare as ak
    for code in TEST_CODES:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                    start_date=START_DATE, end_date=END_DATE, adjust='hfq')
            if df is not None and not df.empty:
                print(f"  {code}: OK (rows={len(df)}, range={df.iloc[0,0]}~{df.iloc[-1,0]})")
                results[f'akshare_{code}'] = {'ok': True, 'rows': len(df), 
                    'first': str(df.iloc[0,0]), 'last': str(df.iloc[-1,0])}
            else:
                print(f"  {code}: Empty")
                results[f'akshare_{code}'] = {'ok': False, 'error': 'Empty'}
        except Exception as e:
            print(f"  {code}: FAIL - {e}")
            results[f'akshare_{code}'] = {'ok': False, 'error': str(e)[:100]}
except Exception as e:
    print(f"  Import error: {e}")

# ============================
# 2. Baostock
# ============================
print("\n" + "=" * 60)
print("2. Baostock")
print("=" * 60)
try:
    import baostock as bs
    lg = bs.login()
    if lg.error_code != '0':
        print(f"  Login failed: {lg.error_msg}")
    else:
        print(f"  Login OK")
        for code in TEST_CODES:
            try:
                # Baostock uses sh/sz prefix
                bs_code = 'sh' + code if code.startswith(('5','6')) else 'sz' + code
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    fields='date,close,volume',
                    start_date=START_DATE[:4]+'-'+START_DATE[4:6]+'-'+START_DATE[6:],
                    end_date=END_DATE[:4]+'-'+END_DATE[4:6]+'-'+END_DATE[6:],
                    frequency='d', adjustflag='2'  # 2=fwd adjusted
                )
                data = []
                while rs.next():
                    data.append(rs.get_row_data())
                
                if len(data) > 1:
                    print(f"  {code}({bs_code}): OK (rows={len(data)}, "
                          f"range={data[0][0]}~{data[-1][0]})")
                    results[f'baostock_{code}'] = {'ok': True, 'rows': len(data),
                        'first': data[0][0], 'last': data[-1][0]}
                else:
                    print(f"  {code}({bs_code}): Empty or error: {data}")
                    results[f'baostock_{code}'] = {'ok': False, 'error': str(data)[:100]}
            except Exception as e:
                print(f"  {code}: FAIL - {e}")
                results[f'baostock_{code}'] = {'ok': False, 'error': str(e)[:100]}
        bs.logout()
except Exception as e:
    print(f"  Baostock error: {e}")

# ============================
# 3. Tushare
# ============================
print("\n" + "=" * 60)
print("3. Tushare")
print("=" * 60)
try:
    import tushare as ts
    
    # Check if token is configured
    token = os.environ.get('TUSHARE_TOKEN', ts.get_token())
    if not token:
        print("  No Tushare token found. Need to register.")
        print("  Register at: https://tushare.pro/register")
        # Try without token (limited)
        pro = ts.pro_api()
    else:
        pro = ts.pro_api(token)
    
    # Try fund_daily for ETF data
    for code in TEST_CODES:
        try:
            if code.startswith(('5','6')):
                ts_code = code + '.SH'
            else:
                ts_code = code + '.SZ'
            
            df = pro.fund_daily(ts_code=ts_code, 
                               start_date=START_DATE,
                               end_date=END_DATE,
                               fields='trade_date,close,vol')
            if df is not None and not df.empty:
                print(f"  {code}({ts_code}): OK (rows={len(df)}, "
                      f"range={df.iloc[-1]['trade_date']}~{df.iloc[0]['trade_date']})")
                results[f'tushare_{code}'] = {'ok': True, 'rows': len(df),
                    'first': str(df.iloc[-1]['trade_date']), 'last': str(df.iloc[0]['trade_date'])}
            else:
                print(f"  {code}: Empty")
                results[f'tushare_{code}'] = {'ok': False, 'error': 'Empty'}
        except Exception as e:
            print(f"  {code}: FAIL - {e}")
            results[f'tushare_{code}'] = {'ok': False, 'error': str(e)[:100]}
except Exception as e:
    print(f"  Tushare error: {e}")

# ============================
# 4. efinance
# ============================
print("\n" + "=" * 60)
print("4. efinance")
print("=" * 60)
try:
    import efinance as ef
    for code in TEST_CODES:
        try:
            df = ef.stock.get_quote_history(code, klt=101, fqt=1, 
                                           beg=START_DATE, end=END_DATE)
            if df is not None and not df.empty:
                print(f"  {code}: OK (rows={len(df)}, "
                      f"range={df.iloc[0]['日期']}~{df.iloc[-1]['日期']})")
                results[f'efinance_{code}'] = {'ok': True, 'rows': len(df),
                    'first': str(df.iloc[0]['日期']), 'last': str(df.iloc[-1]['日期'])}
            else:
                print(f"  {code}: Empty")
                results[f'efinance_{code}'] = {'ok': False, 'error': 'Empty'}
        except Exception as e:
            print(f"  {code}: FAIL - {e}")
            results[f'efinance_{code}'] = {'ok': False, 'error': str(e)[:100]}
except Exception as e:
    print(f"  efinance error: {e}")

# ============================
# 5. 腾讯API (direct HTTP)
# ============================
print("\n" + "=" * 60)
print("5. 腾讯API (direct HTTP)")
print("=" * 60)
try:
    import requests
    for code in TEST_CODES:
        try:
            prefix = 'sh' if code.startswith(('5','6')) else 'sz'
            url = f'http://ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,640,qfq'
            resp = requests.get(url, timeout=15)
            data = resp.json()
            
            if 'data' in data and prefix+code in data['data']:
                kline = data['data'][prefix+code]
                if 'qfqday' in kline:
                    rows = len(kline['qfqday'])
                    first = kline['qfqday'][0][0]
                    last = kline['qfqday'][-1][0]
                    print(f"  {code}({prefix}): OK (rows={rows}, range={first}~{last})")
                    results[f'tencent_{code}'] = {'ok': True, 'rows': rows,
                        'first': first, 'last': last}
                else:
                    print(f"  {code}: No qfqday data")
                    results[f'tencent_{code}'] = {'ok': False, 'error': 'No qfqday'}
            else:
                print(f"  {code}: API returned: {str(data)[:200]}")
                results[f'tencent_{code}'] = {'ok': False, 'error': str(data)[:100]}
        except Exception as e:
            print(f"  {code}: FAIL - {e}")
            results[f'tencent_{code}'] = {'ok': False, 'error': str(e)[:100]}
except Exception as e:
    print(f"  requests error: {e}")

# ============================
# Summary
# ============================
print("\n\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
for key, val in results.items():
    status = '✅' if val.get('ok') else '❌'
    print(f"  {status} {key}: {val.get('rows','')} rows, {val.get('first','')}~{val.get('last','')}" 
          if val.get('ok') else f"  {status} {key}: {val.get('error','')}")

print("\nDone!")
