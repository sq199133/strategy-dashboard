"""检查海外ETF的原始收益率"""
import json, pandas as pd, numpy as np
D = r'D:\QClaw_Trading\data\history'

def load(c):
    with open(D+'/'+c+'.json','r',encoding='utf-8') as f:
        raw=json.load(f)
    df=pd.DataFrame(raw['records'])
    df['date']=pd.to_datetime(df['date'])
    return df[df['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

etfs = [('513100','纳指ETF'),('513500','标普500'),('518880','黄金ETF'),
        ('162411','华宝油气'),('513050','中概互联')]

print(f'{"品种":<10}{"起始":<14}{"收盘(首)":<10}{"收盘(末)":<10}{"总涨幅":<10}{"年化":<8}')
print('-'*62)
for c,n in etfs:
    df = load(c)
    df = df[(df['date']>='2017-01-01')&(df['date']<='2026-06-16')]
    s=df.iloc[0]; e=df.iloc[-1]
    pct = e['close']/s['close'] - 1
    y = len(df)/252
    cagr = (1+pct)**(1/y) - 1
    print(f'{n:<10}{str(s["date"].date()):<14}{s["close"]:<10.2f}{e["close"]:<10.2f}{pct*100:<10.1f}{cagr*100:<8.1f}')

# A股对比
print()
print(f'{"品种":<10}{"起始":<14}{"收盘(首)":<10}{"收盘(末)":<10}{"总涨幅":<10}{"年化":<8}')
print('-'*62)
actfs = [('510050','上证50'),('510300','沪深300'),('159915','创业板'),('512100','中证1000')]
for c,n in actfs:
    df = load(c)
    df = df[(df['date']>='2017-01-01')&(df['date']<='2026-06-16')]
    s=df.iloc[0]; e=df.iloc[-1]
    pct = e['close']/s['close'] - 1
    y = len(df)/252
    cagr = (1+pct)**(1/y) - 1
    print(f'{n:<10}{str(s["date"].date()):<14}{s["close"]:<10.2f}{e["close"]:<10.2f}{pct*100:<10.1f}{cagr*100:<8.1f}')
