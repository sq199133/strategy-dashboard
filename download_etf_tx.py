#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download ALL 195 ETF historical data from Tencent API (前复权)
Uses akshare.stock_zh_a_hist_tx() which supports:
- qfq/hfq adjusted prices
- Year-by-year pagination for full history
- No rate limiting (uses Tencent Finance API, not EastMoney)
"""

import sys
import os
import json
import time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Paths
HISTORY_LONG_DIR = r'D:\QClaw_Trading\data\history_long'
ETF_POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
LOG_FILE = os.path.join(HISTORY_LONG_DIR, 'download_log_tx.txt')

# Ensure directory exists
os.makedirs(HISTORY_LONG_DIR, exist_ok=True)

# Load ETF pool
with open(ETF_POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)
etfs = pool.get('data', [])
print('ETF pool: {} ETFs'.format(len(etfs)))

# Parse prefix (sh/sz) from etf_pool config
def get_prefix(code):
    """Determine exchange prefix - uses the 'exchange' field if available"""
    # Default logic: 5xxx/6xxx = sh, others = sz
    if code.startswith(('5', '6')):
        return 'sh'
    return 'sz'

# Stats
total = len(etfs)
downloaded = 0
skipped = 0
failed = []
no_change = 0

# Import here (after stdout setup)
import akshare as ak
import pandas as pd

def download_etf(code, name=''):
    """Download single ETF, return (rows, date_from, date_to) or None on fail"""
    prefix = get_prefix(code)
    symbol = prefix + code
    
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date='20050101',  # start early, API auto-truncates
            end_date='20260613',
            adjust='qfq'
        )
        if df is not None and not df.empty:
            rows = len(df)
            date_from = str(df['date'].iloc[0].date()) if hasattr(df['date'].iloc[0], 'date') else str(df['date'].iloc[0])
            date_to = str(df['date'].iloc[-1].date()) if hasattr(df['date'].iloc[-1], 'date') else str(df['date'].iloc[-1])
            return (rows, date_from, date_to, df)
        else:
            return None
    except Exception as e:
        return None

print('\n=== Starting batch download (Tencent API, 前复权) ===')
print('Time: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
print()

with open(LOG_FILE, 'w', encoding='utf-8') as log:
    log.write('ETF Data Download from Tencent API (前复权)\n')
    log.write('Start: {}\n\n'.format(datetime.now()))
    
    for i, etf in enumerate(etfs):
        code = etf['code']
        name = etf.get('name', '')
        filename = code + '.json'
        filepath = os.path.join(HISTORY_LONG_DIR, filename)
        
        result = None
        status = '?'
        
        try:
            result = download_etf(code, name)
        except Exception as e:
            result = None
        
        if result is not None:
            rows, d_from, d_to, df = result
            
            # Save as weekly data (Friday close) for backtesting compatibility
            # Convert daily to weekly: pick Friday data
            df_daily = df.copy()
            if 'date' in df_daily.columns:
                df_daily['date'] = pd.to_datetime(df_daily['date'])
                df_daily['weekday'] = df_daily['date'].dt.dayofweek
                df_daily['week'] = df_daily['date'].dt.strftime('%Y-W%V')
                
                # Save daily raw data AND weekly data
                # Weekly: keep Friday (weekday=4), or last available day of the week
                weekly = df_daily[df_daily['weekday'] <= 4].groupby('week').last().reset_index()
                weekly_data = []
                for _, row in weekly.iterrows():
                    weekly_data.append({
                        'w': row['week'],
                        'date': row['date'].strftime('%Y-%m-%d'),
                        'close': float(row['close']),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'vol': float(row.get('amount', row.get('volume', 0)))
                    })
                
                # Save to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(weekly_data, f, ensure_ascii=False, indent=2)
                
                downloaded += 1
                status = 'OK'
                msg = '{} {}: {} rows (daily) -> {} weeks (weekly), {}~{}'.format(
                    code, name, len(df_daily), len(weekly_data), d_from, d_to)
            else:
                # Fallback: save daily as-is
                daily_list = df.to_dict(orient='records')
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(daily_list, f, ensure_ascii=False, indent=2)
                downloaded += 1
                status = 'DAILY'
                msg = '{} {}: {} days (daily only), {}~{}'.format(code, name, rows, d_from, d_to)
        else:
            failed.append((code, name))
            status = 'FAIL'
            msg = '{} {}: FAILED'.format(code, name)
        
        log.write('[{}/{}] {} | {}\n'.format(i+1, total, status, msg))
        log.flush()
        
        print('[{}/{}] {} | {}'.format(i+1, total, status, msg))
        
        # Small delay to be gentle
        if i % 10 == 9:
            time.sleep(1)
    
    # Summary
    print('\n=== DONE ===')
    print('Success: {} / {}'.format(downloaded, total))
    print('Failed: {}'.format(len(failed)))
    if failed:
        print('Failed ETFs:')
        for code, name in failed:
            print('  {} - {}'.format(code, name))
    
    log.write('\n=== DONE ===\n')
    log.write('Success: {}/{}\n'.format(downloaded, total))
    log.write('Failed: {}\n'.format(len(failed)))
    log.write('End: {}\n'.format(datetime.now()))

print('\nFull log: {}'.format(LOG_FILE))
