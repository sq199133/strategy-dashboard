#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download ETF historical data using AKShare (fixed version)
- 使用 adjust='hfq' (后复权)
- 日期范围扩展到2010年
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
START_DATE = '20100101'  # 从2010年开始
END_DATE = datetime.now().strftime('%Y%m%d')
DELAY = 1.0  # 延迟（秒），避免API限制

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
        # AKShare ETF historical data (后复权)
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=START_DATE,
            end_date=END_DATE,
            adjust="hfq"  # 后复权
        )
        
        if df is None or df.empty:
            return None
        
        # Standardize column names (handle encoding issues)
        # Typical columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        if len(df.columns) >= 6:
            # Use positional indexing to avoid encoding issues
            df = df.iloc[:, [0, 2, 5]]  # date, close, volume
            df.columns = ['date', 'close', 'volume']
        
        # Convert to weekly data (Friday close)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Resample to weekly
        weekly_close = df['close'].resample('W').last()
        weekly_volume = df['volume'].resample('W').sum()
        weekly = pd.DataFrame({'close': weekly_close, 'volume': weekly_volume})
        weekly = weekly.dropna(subset=['close'])
        
        # Convert to list of [date, close, volume]
        result = []
        for date, row in weekly.iterrows():
            # Format: YYYY-Www (e.g., 2010-W01)
            year, week, _ = date.isocalendar()
            week_str = f'{year}-W{week:02d}'
            result.append({
                'w': week_str,
                'c': float(row['close']),
                'v': int(row['volume']) if pd.notna(row['volume']) else 0
            })
        
        return result
    
    except Exception as e:
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
        return False

def main():
    print("=" * 70)
    print("  AKShare ETF Data Downloader (Fixed)")
    print("=" * 70)
    print(f"  Pool file: {POOL_FILE}")
    print(f"  Output dir: {OUTPUT_DIR}")
    print(f"  Date range: {START_DATE} ~ {END_DATE}")
    print(f"  Adjust: 后复权 (hfq)")
    print("=" * 70)
    
    etfs = load_pool()
    print(f"\nLoaded {len(etfs)} ETFs from pool\n")
    
    success = 0
    failed = 0
    skipped = 0
    
    for i, etf in enumerate(etfs, 1):
        code = etf['code']
        name = etf.get('name', '')
        
        # Determine prefix
        if code.startswith('6') or code.startswith('5'):
            prefix = 'sh'
        else:
            prefix = 'sz'
        
        # Check if already downloaded
        existing_file = os.path.join(OUTPUT_DIR, f'{prefix}{code}.json')
        
        if os.path.exists(existing_file):
            print(f"[{i}/{len(etfs)}] {code} {name} - Skipped (exists)")
            skipped += 1
            continue
        
        print(f"[{i}/{len(etfs)}] {code} {name}", end=" ")
        
        # Download data
        data = download_etf(code, name)
        
        if data is None:
            print("- Failed")
            failed += 1
            time.sleep(DELAY)
            continue
        
        # Save to JSON
        if save_to_json(code, data):
            print(f"- Success ({len(data)} weeks)")
            success += 1
        else:
            print("- Save failed")
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
