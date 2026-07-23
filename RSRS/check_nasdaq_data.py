"""验证跨境ETF数据质量"""
import json, pandas as pd, numpy as np
D = r'D:\QClaw_Trading\data\history'

# 1. 513100 纳指ETF vs 实际纳指100
# 查历史价格: 2017年1月3日收盘价
with open(D+'/513100.json','r',encoding='utf-8') as f:
    raw = json.load(f)
df = pd.DataFrame(raw['records'])
df['date'] = pd.to_datetime(df['date'])
df = df[df['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

# 关键日期检查
for y in [2017,2019,2021,2023,2025,2026]:
    yd = df[df['date'].dt.year==y]
    if len(yd):
        yr = yd.iloc[-1]['close']/yd.iloc[0]['close']-1
        print(f'{y}: {yd.iloc[0]["close"]:.2f} → {yd.iloc[-1]["close"]:.2f} ({yr*100:+.1f}%)')

print(f'\n513100累计: {df.iloc[0]["close"]:.2f} → {df.iloc[-1]["close"]:.2f}')
print(f'纳指100同期: ~5000 → ~19500 (约+290%)')

# 2. 检查其他海外ETF的代码是否有更好的版本
print()
# 513300 是否更好(更新上市的纳指ETF)?
with open(D+'/513300.json','r',encoding='utf-8') as f:
    raw = json.load(f)
df2 = pd.DataFrame(raw['records'])
df2['date'] = pd.to_datetime(df2['date'])
df2 = df2[df2['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)
print(f'513300(纳指ETF2): {len(df2)}行, {df2.iloc[0]["date"].date()} ~ {df2.iloc[-1]["date"].date()}')
print(f'  起: {df2.iloc[0]["close"]:.2f} → 末: {df2.iloc[-1]["close"]:.2f}')

# 3. 检查159941(纳指ETF, 更大规模)
import os
for f in os.listdir(D):
    if f.startswith('159941'):
        with open(D+'/'+f,'r',encoding='utf-8') as ff:
            try: raw=json.load(ff)
            except: break
        df3=pd.DataFrame(raw['records'])
        if 'date' in df3.columns:
            df3['date']=pd.to_datetime(df3['date'])
            df3=df3[df3['close']>0].drop_duplicates('date',keep='last').sort_values('date')
            print(f'{f.replace(".json","")}: {len(df3)}行, {df3.iloc[0]["date"].date()} ~ {df3.iloc[-1]["date"].date()}')
            print(f'  起: {df3.iloc[0]["close"]:.2f} → 末: {df3.iloc[-1]["close"]:.2f}')
