import urllib.request, json, pandas as pd
from datetime import datetime

def get_etf_daily(code):
    """获取ETF日线数据（最近30天）"""
    secid = f'0.{code}'
    # 获取最近30天数据
    url = f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260501&end=20260531'

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        if data and 'data' in data and data['data']:
            klines = data['data'].get('klines', [])
            records = []
            for k in klines:
                parts = k.split(',')
                records.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'vol': float(parts[5]),
                })
            return records
    except Exception as e:
        print(f"获取{code}失败: {e}")
    return []

print("=" * 70)
print("获取今日收盘数据")
print("=" * 70)

for code in ['159902', '160723', '161128']:
    records = get_etf_daily(code)
    if records:
        latest = records[-1]
        print(f"\n{code} 最新数据:")
        print(f"  日期: {latest['date']}")
        print(f"  收盘: {latest['close']:.3f}")
        print(f"  最高: {latest['high']:.3f}")
        print(f"  最低: {latest['low']:.3f}")
        print(f"  成交量: {latest['vol']:.0f}")
    else:
        print(f"\n{code}: 获取数据失败")

print("\n" + "=" * 70)
print(f"数据获取完成 @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
