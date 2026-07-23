"""用requests直接拉雅虎数据（绕过yfinance的curl SSL问题）"""
import json, requests
from datetime import datetime

period1 = int(datetime(2000,1,1).timestamp())
period2 = int(datetime(2026,6,17).timestamp())

for sym,name in [('GC=F','黄金'),('CL=F','原油')]:
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}'
    params = {'period1': period1, 'period2': period2, 'interval': '1d', 'events': 'history'}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, params=params, headers=headers, verify=False)
        data = r.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        closes = quotes['close']
        
        print(f'{name:<6}({sym:<6}): {sum(1 for c in closes if c is not None)}行')
        dates = [datetime.fromtimestamp(t).strftime('%Y-%m-%d') for t in timestamps]
        valid = [(d, c) for d, c in zip(dates, closes) if c is not None]
        if valid:
            print(f'          首:{valid[0][0]} {valid[0][1]:.2f}  末:{valid[-1][0]} {valid[-1][1]:.2f}')
    except Exception as e:
        print(f'{name:<6}({sym:<6}): {str(e)[:100]}')
