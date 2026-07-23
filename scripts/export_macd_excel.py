#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full ETF weekly MACD export to Excel"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
import akshare as ak

POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_FILE = r'D:\QClaw_Trading\signals\macd_weekly_full_20260505.xlsx'
FAST, SLOW, SIGNAL = 12, 26, 9

with open(POOL_FILE, 'r', encoding='utf-8') as f:
    etfs = json.load(f)['data']
print(f"Pool: {len(etfs)} ETFs")

rows = []
failed = []

for i, etf in enumerate(etfs):
    code = str(etf['code'])
    name = etf.get('name', '')
    cat = etf.get('category', '')

    if (i + 1) % 20 == 0:
        print(f"{i+1}/{len(etfs)}")

    try:
        df = ak.fund_etf_hist_em(symbol=code, period="weekly", adjust="qfq")
        if df is None or len(df) < SLOW + SIGNAL + 5:
            failed.append({'code': code, 'name': name, 'error': 'data_insufficient'})
            time.sleep(0.2)
            continue

        df.columns = ['date','open','close','high','low','vol','amount','amp','pct','chg','turnover']
        df['date'] = pd.to_datetime(df['date'])
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)

        dif = df['close'].ewm(span=FAST, adjust=False).mean() - df['close'].ewm(span=SLOW, adjust=False).mean()
        dea = dif.ewm(span=SIGNAL, adjust=False).mean()
        macd_hist = 2 * (dif - dea)

        dif_t = float(dif.iloc[-1])
        dif_p = float(dif.iloc[-2])
        dea_t = float(dea.iloc[-1])
        macd_t = float(macd_hist.iloc[-1])
        close_t = float(df['close'].iloc[-1])
        date_t = str(df['date'].iloc[-1].date())

        if dif_t > 0 and dif_p <= 0:
            sig = 'BUY'
        elif dif_t < 0 and dif_p >= 0:
            sig = 'SELL'
        elif dif_t > 0:
            sig = 'LONG'
        else:
            sig = 'SHORT'

        rows.append({
            'Code': code,
            'Name': name,
            'Category': cat,
            'Date': date_t,
            'Close': round(close_t, 4),
            'DIF': round(dif_t, 6),
            'DEA': round(dea_t, 6),
            'MACD_Hist': round(macid_t, 6),
            'DIF_Prev': round(dif_p, 6),
            'DIF_Change': round(dif_t - dif_p, 6),
            'Signal': sig,
        })
    except Exception as e:
        failed.append({'code': code, 'name': name, 'error': str(e)[:80]})

    time.sleep(0.2)

print(f"OK: {len(rows)}, Fail: {len(failed)}")

df_all = pd.DataFrame(rows)

sig_order = {'BUY': 0, 'SELL': 1, 'LONG': 2, 'SHORT': 3}
df_all['_s'] = df_all['Signal'].map(sig_order)
df_all = df_all.sort_values(['_s', 'DIF'], ascending=[True, False]).drop(columns=['_s']).reset_index(drop=True)

df_buy = df_all[df_all['Signal'] == 'BUY']
df_sell = df_all[df_all['Signal'] == 'SELL']
df_fail = pd.DataFrame(failed) if failed else pd.DataFrame()

with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
    df_all.to_excel(writer, sheet_name='ALL', index=False)
    df_buy.to_excel(writer, sheet_name='BUY', index=False)
    df_sell.to_excel(writer, sheet_name='SELL', index=False)
    if not df_fail.empty:
        df_fail.to_excel(writer, sheet_name='FAILED', index=False)

print(f"\nSaved: {OUTPUT_FILE}")
print(f"  ALL={len(df_all)}  BUY={len(df_buy)}  SELL={len(df_sell)}  FAIL={len(failed)}")
os.startfile(OUTPUT_FILE)
