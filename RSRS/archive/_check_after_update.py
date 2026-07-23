"""检查用户更新数据后的状态"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DATA = r'D:\QClaw_Trading\data\history'
codes = ['510050','510300','510500','512100','159915',
         '588000','513500','513100','518880','162411','515080']
names = {'510050':'上证50','510300':'沪深300','510500':'中证500',
         '512100':'中证1000','159915':'创业板','588000':'科创50',
         '513500':'标普500','513100':'纳斯达克','518880':'黄金',
         '162411':'原油','515080':'中证红利'}

total = len([f for f in os.listdir(DATA) if f.endswith('.json')])
print(f'data/history 目录: 共 {total} 个JSON文件\n')

for code in codes:
    path = os.path.join(DATA, code+'.json')
    if not os.path.exists(path):
        print(f'{code:>6} {names.get(code,"?"):<8}  ❌ 缺失')
        continue
    sz = os.path.getsize(path)
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    records = raw.get('records', raw.get('data', raw if isinstance(raw,list) else [raw]))
    dates = sorted(set(r.get('date',r.get('day','')) for r in records if r.get('date') or r.get('day')))
    n = len(records)
    rng = f'{dates[0][:10]} ~ {dates[-1][:10]}' if dates else 'N/A'
    
    if n < 200:
        st = '⚠️ 仅101天'
    elif n >= 2000:
        st = '✅ 完整'
    elif n >= 1200:
        st = '✅ M=1200够用'
    else:
        st = f'⚡ 不足({n}天)'
    
    print(f'{code:>6} {names.get(code,"?"):<8}  {n:>5}条  {rng}  {st}')

print()

# 验证RSRS现可计算
import numpy as np
with open(os.path.join(DATA, '510300.json'), encoding='utf-8') as f:
    raw = json.load(f)
records = raw.get('records', raw.get('data', raw if isinstance(raw,list) else [raw]))
dates = [r['date'][:10] for r in records]
print(f'HS300 最新日期: {dates[-1]}')
print(f'HS300 最早日期: {dates[0]}')
