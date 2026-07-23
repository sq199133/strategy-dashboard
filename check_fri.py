"""Check if 2026-06-26 data exists for 159928"""
from qclaw_stock_data import DataFetcher
f = DataFetcher()
data = f.kline('159928', 50)
if data:
    print(f'Total: {len(data)} rows')
    print('Last 5:')
    for row in data[-5:]:
        print(f'  {row["date"]} close={row["close"]}')
else:
    print('No data')
