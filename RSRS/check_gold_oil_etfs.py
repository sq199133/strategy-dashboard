"""检查本地黄金/油气ETF及商品指数详情"""
import json, os

D = r'D:\QClaw_Trading\data\history'

# 黄金相关的ETF
print('=== 本地黄金ETF ===')
for f in sorted(os.listdir(D)):
    if '黄金' in f or 'gold' in f.lower() or f.startswith('518880') or f.startswith('159934'):
        fp = os.path.join(D, f)
        with open(fp,'r',encoding='utf-8') as fh:
            raw = json.load(fh)
            recs = raw['records']
        dates = [r['date'] for r in recs if 'date' in r]
        closes = [r['close'] for r in recs if 'close' in r and r['close'] and r['close'] > 0]
        if closes:
            ret = (closes[-1]/closes[0] - 1)*100
            yrs = len(closes)/250
            cagr = (closes[-1]/closes[0])**(1/yrs)-1 if yrs > 0 else 0
            print(f'  {f:<35}: {len(closes):>4}行 {dates[0][:10]}~{dates[-1][:10]}  {ret:+.1f}%({cagr*100:.1f}%/年)')

# 油气相关的ETF
print('\n=== 本地原油/石油ETF ===')
kw = ['原油','石油','油气','能源']
for f in sorted(os.listdir(D)):
    if any(k in f for k in kw):
        fp = os.path.join(D, f)
        with open(fp,'r',encoding='utf-8') as fh:
            raw = json.load(fh)
            recs = raw['records']
        dates = [r['date'] for r in recs if 'date' in r]
        closes = [r['close'] for r in recs if 'close' in r and r['close'] and r['close'] > 0]
        if closes:
            ret = (closes[-1]/closes[0]-1)*100
            yrs = len(closes)/250
            cagr = (closes[-1]/closes[0])**(1/yrs)-1 if yrs > 0 else 0
            print(f'  {f:<35}: {len(closes):>4}行 {dates[0][:10]}~{dates[-1][:10]}  {ret:+.1f}%({cagr*100:.1f}%/年)')
