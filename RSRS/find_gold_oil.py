"""找黄金/原油的中国端数据"""
import akshare as ak
import warnings; warnings.filterwarnings('ignore')

# 1. 黄金ETF (518880) - 本地数据
import json, os
D = r'D:\QClaw_Trading\data\history'
gold_files = [f for f in os.listdir(D) if f.startswith('518880')]
print(f'黄金ETF(518880): {gold_files}')
for f in sorted(gold_files):
    with open(os.path.join(D, f), 'r', encoding='utf-8') as ff:
        raw = json.load(ff)
    recs = raw['records']
    dates = [r['date'] for r in recs if 'date' in r]
    closes = [r['close'] for r in recs if 'close' in r and r['close'] and r['close'] > 0]
    print(f'  {len(closes)}行  {dates[0][:10]} ~ {dates[-1][:10]}  {closes[0]:.2f} -> {closes[-1]:.2f}')

# 2. 用新浪API直接拉黄金现货/期货数据
print()
print('=== 黄金/商品指数备选 ===')
# 试一些可能的黄金指数代码
for sym in ['sh000066','sz399972','sh000015','sz399997']:
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
        print(f'{sym}: {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
    except Exception as e:
        print(f'{sym}: {str(e)[:60]}')

# 3. 试试global_hist_sina的不同格式
print()
for sym in ['gold','xau','goldusd','xauusd']:
    try:
        df = ak.index_global_hist_sina(symbol=sym)
        print(f'global_sina({sym}): {len(df)}行')
    except:
        pass

print()
# 4. 试试stock_zh_index_daily_em(东方财富) - 虽然之前ConnectionAborted, 再试一次
for sym in ['csi931151','csi931152']:
    try:
        df = ak.stock_zh_index_daily_em(symbol=sym)
        print(f'stock_zh_daily_em({sym}): {len(df)}行 {df.iloc[0]["日期"]}')
    except:
        print(f'stock_zh_daily_em({sym}): 不可用')
