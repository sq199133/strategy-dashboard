"""Check 6/19 data via different APIs"""
import requests

# Sina API - last 20 days
url = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz159928&scale=240&datalen=20'
r = requests.get(url, timeout=15)
data = r.json()
print('Sina API (last 20):')
for row in data[-20:]:
    print(f'  {row["day"]}')

print()

# Tencent API
url2 = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz159928,day,,,50,'
r2 = requests.get(url2, timeout=15)
j = r2.json()
rows = j.get('data', {}).get('sz159928', {}).get('day', [])
print('Tencent (last 20):')
for row in rows[-20:]:
    print(f'  {row[0]} close={row[2]}')

# Also check 6/22 (should be trading day)
print()
print('Looking for 6/19 and 6/22 specifically:')
all_dates = [row['day'].split()[0] for row in data]
for d in ['2026-06-18', '2026-06-19', '2026-06-20', '2026-06-21', '2026-06-22', '2026-06-23']:
    status = 'IN Sina' if d in all_dates else 'MISSING'
    print(f'  {d}: {status}')
