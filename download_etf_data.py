#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download ETF historical data using AKShare
- 使用 akshare.fund_etf_hist_em() 下载日线数据
- 转换为周线并保存为JSON格式
- 支持断点续传和错误处理
"""

import json
import os
import sys
import time
import pandas as pd
from datetime import datetime

try:
    import akshare as ak
    HAS_AK = True
except Exception as e:
    print(f"AKShare not available: {e}")
    HAS_AK = False
    sys.exit(1)

# Configuration
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\QClaw_Trading\data\history_long'
START_DATE = '20100101'  # 从2010年开始下载
END_DATE = datetime.now().strftime('%Y%m%d')
DELAY = 0.5  # 延迟（秒），避免API限制

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_pool():
    """Load ETF pool from JSON file."""
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def download_etf(code, name=''):
    """Download single ETF data using AKShare."""
    try:
        # AKShare ETF historical data
        # symbol: ETF代码（如510880）
        # period: daily/weekly/monthly
        # start_date/end_date: YYYYMMDD格式
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=START_DATE,
            end_date=END_DATE,
            adjust="f"  # 前复权
        )
        
        if df is None or df.empty:
            return None
        
        # Standardize column names
        df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'amplitude', 'pct_change', 'pct_change2', 'turnover']
        
        # Convert to weekly data
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Resample to weekly (Friday close)
        weekly = df['close'].resample('W').last()
        weekly = weekly.dropna()
        
        # Convert to list of [date, close]
        result = []
        for date, close in weekly.items():
            week_str = date.strftime('%Y-W%U')  # Format: 2010-W01
            result.append([week_str, float(close)])
        
        return result
    
    except Exception as e:
        print(f"  Error downloading {code}: {e}")
        return None

def save_to_json(code, data):
    """Save data to JSON file."""
    # Determine prefix (sh/sz)
    if code.startswith('6') or code.startswith('5'):
        prefix = 'sh'
    else:
        prefix = 'sz'
    
    filename = f'{prefix}{code}.json'
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"  Error saving {code}: {e}")
        return False

def main():
    print("=" * 70)
    print("  AKShare ETF Data Downloader")
    print("=" * 70)
    print(f"  Pool file: {POOL_FILE}")
    print(f"  Output dir: {OUTPUT_DIR}")
    print(f"  Date range: {START_DATE} ~ {END_DATE}")
    print("=" * 70)
    
    etfs = load_pool()
    print(f"\nLoaded {len(etfs)} ETFs from pool\n")
    
    success = 0
    failed = 0
    skipped = 0
    
    for i, etf in enumerate(etfs, 1):
        code = etf['code']
        name = etf.get('name', '')
        
        print(f"[{i}/{len(etfs)}] {code} {name}")
        
        # Check if already downloaded
        if code.startswith('6') or code.startswith('5'):
            prefix = 'sh'
        else:
            prefix = 'sz'
        existing_file = os.path.join(OUTPUT_DIR, f'{prefix}{code}.json')
        
        if os.path.exists(existing_file):
            print(f"  Skipped (already exists)")
            skipped += 1
            continue
        
        # Download data
        data = download_etf(code, name)
        
        if data is None:
            print(f"  Failed")
            failed += 1
            time.sleep(DELAY)
            continue
        
        # Save to JSON
        if save_to_json(code, data):
            print(f"  Success ({len(data)} weeks)")
            success += 1
        else:
            print(f"  Save failed")
            failed += 1
        
        # Rate limiting
        time.sleep(DELAY)
        
        # Progress save every 10 ETFs
        if i % 10 == 0:
            print(f"\n  Progress: {i}/{len(etfs)} ({i/len(etfs)*100:.1f}%)")
            print(f"  Success: {success}, Failed: {failed}, Skipped: {skipped}\n")
    
    print("=" * 70)
    print("  Download Complete")
    print("=" * 70)
    print(f"  Total: {len(etfs)}")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print("=" * 70)

if __name__ == '__main__':
    main()
