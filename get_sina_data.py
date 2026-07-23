import requests, json, pandas as pd
from datetime import datetime, timedelta

def get_sina_data(code):
    """从新浪财经获取ETF数据"""
    # 159902 -> sz159902
    if code.startswith('15') or code.startswith('16'):
        symbol = f"sz{code}"
    else:
        symbol = f"sh{code}"

    # 获取实时行情
    url = f"http://hq.sinajs.cn/list={symbol}"

    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gbk'
        text = resp.text

        if 'var hq_str' in text:
            data = text.split('"')[1].split(',')
            if len(data) > 30:
                return {
                    'code': code,
                    'name': data[0],
                    'close': float(data[3]),  # 当前价
                    'open': float(data[1]),
                    'high': float(data[4]),
                    'low': float(data[5]),
                    'pre_close': float(data[2]),
                }
    except Exception as e:
        print(f"获取{code}失败: {e}")
    return None

print("=" * 70)
print("从新浪财经获取实时行情")
print("=" * 70)

for code in ['159902', '160723', '161128']:
    data = get_sina_data(code)
    if data:
        print(f"\n{code} {data['name']}")
        print(f"  最新价: {data['close']:.3f}")
        print(f"  今开: {data['open']:.3f}")
        print(f"  最高: {data['high']:.3f}")
        print(f"  最低: {data['low']:.3f}")
        print(f"  昨收: {data['pre_close']:.3f}")
        change = (data['close'] - data['pre_close']) / data['pre_close'] * 100
        print(f"  涨跌: {change:+.2f}%")
    else:
        print(f"\n{code}: 获取失败")

print("\n" + "=" * 70)
print(f"数据获取完成 @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
