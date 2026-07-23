# -*- coding: utf-8 -*-
"""计算RSRS信号、12-1动量、估值分位"""
import os, json, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

DATA = r'D:\QClaw_Trading\data\history'
OUT = r'D:\QClaw_Trading\RSRS'

def load_etf(code):
    path = os.path.join(DATA, code + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        recs = raw.get('records', raw.get('data', []))
    else:
        recs = raw
    df = pd.DataFrame(recs)
    dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
    cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
    hc = next((c for c in df.columns if c.lower() in ['high','h']), None)
    lc = next((c for c in df.columns if c.lower() in ['low','l']), None)
    if not dc or not cc: return None
    df['date'] = pd.to_datetime(df[dc])
    for col, name in [(cc,'close'),(hc,'high'),(lc,'low')]:
        if col: df[name] = pd.to_numeric(df[col], errors='coerce')
    return df[['date','close','high','low']].dropna().drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

# ── RSRS ──
def rsrs(df, n=18, m=900):
    H, L = df['high'].values, df['low'].values
    beta = np.full(len(df), np.nan)
    for i in range(n-1, len(df)):
        x, y = L[i-n+1:i+1], H[i-n+1:i+1]
        if not (np.isnan(x).any() or np.isnan(y).any()):
            xm = np.column_stack([np.ones(n), x])
            try: beta[i] = np.linalg.lstsq(xm, y, rcond=None)[0][1]
            except: pass
    z = np.full(len(beta), np.nan)
    for i in range(m-1, len(beta)):
        v = beta[i-m+1:i+1]; vv = v[~np.isnan(v)]
        if len(vv) >= 100:
            mu, sg = np.mean(vv), np.std(vv, ddof=1)
            if sg > 0: z[i] = (beta[i] - mu) / sg
    return beta, z

# ── 12-1动量 ──
def momentum_11(monthly_prices):
    """过去11月动量（不含当月）"""
    if len(monthly_prices) < 12: return np.nan
    p = monthly_prices.iloc[-12] if len(monthly_prices) >= 13 else monthly_prices.iloc[0]
    e = monthly_prices.iloc[-2]
    return e / p - 1 if p > 0 else np.nan

# ── 估值分位 ──
def val_score(close_arr, idx, window=252, min_w=126):
    ptm = close_arr / pd.Series(close_arr).rolling(12, min_periods=6).mean().values
    if idx < window: return 0.5
    w = ptm[max(0,idx-window):idx]
    v = w[~np.isnan(w)]
    if len(v) < min_w: return 0.5
    return (v > ptm[idx]).sum() / len(v)

# ── 主计算 ──
print('加载数据...')
df300 = load_etf('510300')
etfs = {'510300':'沪深300','510500':'中证500','512100':'中证1000',
        '159915':'创业板指','588080':'科创50','510050':'上证50'}

# 1. RSRS
print('计算RSRS...')
beta, zscore = rsrs(df300, n=18, m=900)
valid = ~np.isnan(zscore)
beta_v, z_v = beta[valid], zscore[valid]
dates_rsrs = df300['date'].values[valid]

# 最新RSRS
last_beta = beta_v[-1]
last_z = z_v[-1]
last_date = pd.Timestamp(dates_rsrs[-1])
pos = 1 if last_z > 0.7 else (0 if last_z < -1.0 else -1)  # 1=买入,0=卖出,-1=观望
print(f'RSRS: date={last_date.date()} z={last_z:.3f} beta={last_beta:.3f} signal={pos}')

# 2. 月度12-1动量
print('计算12-1动量...')
mom_results = {}
for code, name in etfs.items():
    df = load_etf(code)
    if df is None: continue
    df['month'] = df['date'].dt.to_period('M')
    monthly = df.groupby('month').agg(close=('close','last')).reset_index()
    if len(monthly) < 13: continue
    mom = momentum_11(monthly['close'])
    mom_results[name] = round(mom*100, 2) if mom is not None and not np.isnan(mom) else None

# 排序
sorted_mom = sorted([(k,v) for k,v in mom_results.items() if v is not None],
                    key=lambda x: -x[1])
print('12-1动量排名:', [(n,r) for n,r in sorted_mom])

# 3. 估值分位
print('计算估值分位...')
val_results = {}
for code, name in etfs.items():
    df = load_etf(code)
    if df is None: continue
    closes = df['close'].values
    if len(closes) < 252: continue
    vs = val_score(closes, len(closes)-1)
    val_results[name] = round(vs, 3)

print('估值分位:', val_results)

# 4. 当日涨跌
rt_data = {"沪深300":{"chg_pct":"-3.60"},"中证500":{"chg_pct":"-5.55"},
           "中证1000":{"chg_pct":"-6.08"},"创业板指":{"chg_pct":"-7.15"},
           "科创50":{"chg_pct":"-7.12"},"上证50":{"chg_pct":"-3.50"}}

# ── 输出JSON ──
output = {
    'rsrs': {
        'date': str(last_date.date()),
        'zscore': round(float(last_z), 3),
        'beta': round(float(last_beta), 3),
        'signal': pos,  # 1=买入,0=卖出,-1=观望
        'signal_text': {1:'买入信号',0:'卖出信号',-1:'观望'}[pos],
        'buy_thr': 0.7,
        'sell_thr': -1.0
    },
    'momentum_12_1': {name: val for name, val in sorted_mom},
    'valuation': val_results,
    'daily_chg': rt_data
}

with open(r'D:\QClaw_Trading\_dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print('数据已保存到 _dashboard_data.json')
