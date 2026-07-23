#!/usr/bin/env python3
"""Verify Sina ETF data - is it adjusted?"""
import sys, json, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import akshare as ak

# 1. Sina data
sina = ak.fund_etf_hist_sina(symbol='sh510880')
# Convert Sina dates to string YYYY-MM-DD for comparison
sina['date_str'] = sina['date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
sina_dict = dict(zip(sina['date_str'].values, sina['close'].values))
print('Sina date sample:', list(sina['date_str'].values)[-5:])

# 2. Tencent API data
resp = requests.get('http://ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh510880,day,,,640,qfq', timeout=10)
tencent = resp.json()
kline = tencent['data']['sh510880']['qfqday']
print('Tencent date sample:', [r[0] for r in kline[-5:]])

# 3. Compare dates
sina_dates = set(sina['date'].values)
tencent_dates = set(r[0] for r in kline)
common = sina_dates & tencent_dates
print('\nCommon dates: {}'.format(len(common)))
print('Sina only: {}'.format(len(sina_dates - tencent_dates)))
print('Tencent only: {}'.format(len(tencent_dates - sina_dates)))

# 4. Compare close prices on common dates
match = 0
diff = 0
for row in kline:
    dt = row[0]
    t_close = float(row[2])
    if dt in sina_dict:
        s_close = sina_dict[dt]
        if abs(s_close - t_close) / max(t_close, 0.01) * 100 < 0.5:
            match += 1
        else:
            if diff < 3:
                print('  Diff: {} sina={:.3f} tencent={:.3f} ({:.2f}%)'.format(
                    dt, s_close, t_close, 
                    abs(s_close - t_close) / t_close * 100))
            diff += 1

print('\nMatch (diff<0.5%): {}/{} ({:.1f}%)'.format(match, match+diff, match/(match+diff)*100 if (match+diff) else 0))
print('Diff: {}'.format(diff))
if match > 0 and match/(match+diff) > 0.95:
    print('CONCLUSION: Sina data IS adjusted (前复权)')
elif diff > 0 and diff/(match+diff) > 0.5:
    print('CONCLUSION: Sina data is NOT 前复权 (unadjusted)')
else:
    print('CONCLUSION: Uncertain pattern')
