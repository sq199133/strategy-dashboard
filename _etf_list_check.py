# -*- coding: utf-8 -*-
import os, json, pandas as pd, numpy as np

OUT_DIR = r'D:\QClaw_Trading'
DATA = os.path.join(OUT_DIR, 'data', 'history')

etfs = {
    '510300': '沪深300',
    '510500': '中证500',
    '512100': '中证1000',
    '159915': '创业板指',
    '588080': '科创50',
    '510100': '上证50',
}

all_data = {}
for code, name in etfs.items():
    path = os.path.join(DATA, f'{code}.json')
    if not os.path.exists(path):
        print(f'缺失: {code}')
        continue
    with open(path, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    if isinstance(raw, list): df = pd.DataFrame(raw)
    elif 'data' in raw: df = pd.DataFrame(raw['data'])
    elif 'records' in raw: df = pd.DataFrame(raw['records'])
    else:
        print(f'{code} 格式异常: {type(raw)}')
        continue
    dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
    cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
    if not dc or not cc:
        print(f'{code} 缺字段: {list(df.columns)}')
        continue
    df['date'] = pd.to_datetime(df[dc])
    df['close'] = pd.to_numeric(df[cc], errors='coerce')
    df = df.dropna(subset=['date','close']).sort_values('date')
    all_data[name] = df
    print(f'{name}({code}): {df["date"].min().date()}~{df["date"].max().date()}, {len(df)}行, 最后价格={df["close"].iloc[-1]:.3f}')

print(f'\n共{len(all_data)}个指数')
