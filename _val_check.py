# -*- coding: utf-8 -*-
import pandas as pd, numpy as np, os

OUT = r'D:\QClaw_Trading\data\index_val'
for name in ['沪深300','中证500','中证1000','创业板指','科创50']:
    path = os.path.join(OUT, f'{name}.csv')
    if not os.path.exists(path):
        print(f'{name}: 文件不存在')
        continue
    df = pd.read_csv(path)
    df = df.dropna(subset=['val_score'])
    if df.empty:
        print(f'{name}: 无val_score')
        continue
    last = df.iloc[-1]
    vs = last['val_score']
    ptm = last['price_to_ma']
    label = '低估' if vs > 0.7 else ('高估' if vs < 0.3 else '中性')
    print(f'{name}: val_score={vs:.3f}({label})  price/MA12={ptm:.3f}({((ptm-1)*100):+.1f}%)  date={last["date"]}')
