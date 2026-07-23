# -*- coding: utf-8 -*-
"""估值分位现状检查"""
import os, json, pandas as pd, numpy as np

OUT_DIR = r'D:\QClaw_Trading'
DATA = os.path.join(OUT_DIR, 'data', 'history')

etfs = {
    '510300': '沪深300',
    '510500': '中证500',
    '512100': '中证1000',
    '159915': '创业板指',
    '588080': '科创50',
}

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

print('=== 当前估值分位（2026年7月）===')
for name, df in all_data.items():
    # 月末
    df = df.copy()
    df['month'] = df['date'].dt.to_period('M')
    m = df.groupby('month').agg(close=('close','last')).reset_index()
    m['date'] = m['month'].dt.to_timestamp()
    m = m.sort_values('date')
    
    # 计算ma12
    m['ma12'] = m['close'].rolling(12, min_periods=6).mean()
    m['price_to_ma'] = m['close'] / m['ma12']
    
    # 滚动60月分位
    vals = m['price_to_ma'].values
    pct = np.full(len(vals), np.nan)
    for i in range(60, len(vals)):
        window = vals[max(0, i-60):i]
        valid = window[~np.isnan(window)]
        if len(valid) >= 36:
            pct[i] = (valid > vals[i]).sum() / len(valid)
    m['val_score'] = pct
    
    last = m.dropna(subset=['val_score']).iloc[-1]
    vs = last['val_score']
    ptm = last['price_to_ma']
    label = '低估 ✓' if vs > 0.7 else ('高估 ✗' if vs < 0.3 else '中性 -')
    print(f'  {name}: val_score={vs:.3f} {label}  price/MA12={ptm:.3f} ({((ptm-1)*100):+.1f}%)')
