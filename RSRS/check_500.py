"""检查中证500 ETF数据和替代标的"""
import json, os
D = r'D:\QClaw_Trading\data\history'

# 中证500相关
for f in os.listdir(D):
    if '500' in f and f.endswith('.json') and len(f) < 10:
        print(f.replace('.json',''), end=' ')
print()
# 其他替代
for f in os.listdir(D):
    if f[:6] in ('512500','515800','560500','561350'):
        print(f.replace('.json',''), end=' ')
print()

# 510500详细
with open(D+'/510500.json','r',encoding='utf-8') as f:
    raw = json.load(f)
recs = raw['records']
print(f'\n510500: {len(recs)} rows, {recs[0]["date"]} ~ {recs[-1]["date"]}')
print(f'code={raw.get("code","?")}, name={raw.get("name","?")}')
print(f'sample: {recs[:3]}')
print(f'sample tail: {recs[-3:]}')
