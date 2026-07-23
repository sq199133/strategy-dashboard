"""测试AKShare指数接口"""
import akshare as ak

# 国内指数
domestic = {
    '沪深300': 'sh000300',
    '上证50': 'sh000016',
    '中证500': 'sh000905',
    '中证1000': 'sh000852',
    '创业板': 'sz399006',
    '科创50': 'sh000688',
}

print('=== 国内指数 ===')
for name, sym in domestic.items():
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
        print(f'  {name:<8} {sym:<12}: {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
        print(f'          首: {df.iloc[0]["close"]:.2f}  末: {df.iloc[-1]["close"]:.2f}')
    except Exception as e:
        print(f'  {name:<8} {sym:<12}: ERR {str(e)[:100]}')

# 国际指数
print()
print('=== 国际指数 ===')
overseas = ['^GSPC', '^IXIC', '^DJI', '^HSI', 'GC=F']
for sym in overseas:
    try:
        df = ak.index_investing_global(symbol=sym)
        print(f'  {sym:<10}: {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
    except Exception as e:
        print(f'  {sym:<10}: ERR {str(e)[:100]}')

# 也可以试试ak.us_index_xxx
print()
print('=== US指数(备用) ===')
try:
    df = ak.us_index_hist(symbol='SPX')
    print(f'  SPX: {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
except Exception as e:
    print(f'  SPX ERR: {str(e)[:100]}')
