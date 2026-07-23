import urllib.request, json, datetime

def get_realtime_quote(code):
    '''获取ETF实时行情'''
    secid = f'0.{code}'  # 0=深交所
    url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f60,f170,f171'

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data and 'data' in data and data['data']:
            d = data['data']
            return {
                'code': code,
                'name': d.get('f58', ''),
                'close': d.get('f43', 0) / 100 if d.get('f43') else None,
                'change_pct': d.get('f170', 0) / 100 if d.get('f170') else None,
                'high': d.get('f44', 0) / 100 if d.get('f44') else None,
                'low': d.get('f45', 0) / 100 if d.get('f45') else None,
            }
    except Exception as e:
        return {'code': code, 'error': str(e)}
    return {'code': code, 'error': 'no data'}

print('=' * 70)
print('实时行情 -', datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
print('=' * 70)

quotes = []
for code in ['159902', '160723', '161128']:
    q = get_realtime_quote(code)
    quotes.append(q)
    if 'error' in q:
        print(f"{code}: 获取失败 - {q['error']}")
    else:
        print(f"{code} {q['name']}")
        print(f"  最新价: {q['close']:.3f}  涨跌: {q['change_pct']:+.2f}%")
        print(f"  最高: {q['high']:.3f}  最低: {q['low']:.3f}")
        print()

# 输出收盘价供后续计算
print('=' * 70)
print('收盘价汇总（用于布林带计算）')
print('=' * 70)
for q in quotes:
    if 'close' in q and q['close']:
        print(f"{q['code']}: {q['close']:.3f}")
