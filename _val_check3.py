# -*- coding: utf-8 -*-
"""估值分位检查"""
import os, json, pandas as pd, numpy as np

OUT_DIR = r'D:\QClaw_Trading'
DATA = os.path.join(OUT_DIR, 'data', 'history')

etfs = {'510300':'沪深300','510500':'中证500','512100':'中证1000','159915':'创业板指','588080':'科创50'}
all_data = {}
for code, name in etfs.items():
    path = os.path.join(DATA, f'{code}.json')
    with open(path, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    if isinstance(raw, list): df = pd.DataFrame(raw)
    elif 'data' in raw: df = pd.DataFrame(raw['data'])
    elif 'records' in raw: df = pd.DataFrame(raw['records'])
    else: continue
    dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
    cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
    if not dc or not cc: continue
    df['date'] = pd.to_datetime(df[dc])
    df['close'] = pd.to_numeric(df[cc], errors='coerce')
    df = df.dropna(subset=['date','close']).sort_values('date').reset_index(drop=True)
    df['ret'] = df['close'].pct_change()
    all_data[name] = df

print('=== 估值分位现状 (2026-07) ===')
for name, df in all_data.items():
    m = df.copy()
    m['month'] = m['date'].dt.to_period('M')
    monthly = m.groupby('month').agg(close=('close','last')).reset_index()
    monthly['date'] = monthly['month'].dt.to_timestamp()
    monthly = monthly.sort_values('date')
    monthly['ma12'] = monthly['close'].rolling(12, min_periods=6).mean()
    monthly['price_to_ma'] = monthly['close'] / monthly['ma12']
    vals = monthly['price_to_ma'].values
    pct = np.full(len(vals), np.nan)
    for i in range(60, len(vals)):
        window = vals[max(0, i-60):i]
        valid = window[~np.isnan(window)]
        if len(valid) >= 36:
            pct[i] = (valid > vals[i]).sum() / len(valid)
    monthly['val_score'] = pct
    last = monthly.dropna(subset=['val_score']).iloc[-1]
    vs = last['val_score']
    ptm = last['price_to_ma']
    if vs > 0.7: label = '低估'
    elif vs < 0.3: label = '高估'
    else: label = '中性'
    print(f'{name}: val_score={vs:.3f}({label})  P/MA12={ptm:.3f}({((ptm-1)*100):+.1f}%)')
