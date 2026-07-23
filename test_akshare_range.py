#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple ETF data download test - only test 3 ETFs"""

import json
import os
import sys
import time
import pandas as pd
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import akshare as ak
    HAS_AK = True
except Exception as e:
    print("AKShare not available: " + str(e))
    HAS_AK = False
    sys.exit(1)

def test_download(code):
    """Test download for single ETF."""
    print("Testing " + code + "...")
    
    try:
        # Try to download data (try both adjust options)
        for adjust in ['hfq', '']:
            try:
                df = ak.fund_etf_hist_em(
                    symbol=code,
                    period="daily",
                    start_date='20100101',
                    end_date='20260613',
                    adjust=adjust
                )
                
                if df is not None and not df.empty:
                    print("  adjust='" + adjust + "': SUCCESS (rows=" + str(len(df)) + ")")
                    print("  Date range: " + str(df.iloc[0, 0]) + " ~ " + str(df.iloc[-1, 0]))
                    
                    # Convert to weekly
                    df['date'] = pd.to_datetime(df.iloc[:, 0])
                    df.set_index('date', inplace=True)
                    weekly = df.iloc[:, 1].resample('W').last()
                    weekly = weekly.dropna()
                    
                    print("  Weekly data: " + str(len(weekly)) + " weeks")
                    print("  First week: " + str(weekly.index[0].strftime('%Y-%m-%d')))
                    print("  Last week: " + str(weekly.index[-1].strftime('%Y-%m-%d')))
                    return True
                    
            except Exception as e:
                print("  adjust='" + adjust + "': Error - " + str(e))
        
        return False
        
    except Exception as e:
        print("  Error: " + str(e))
        return False

# Test with 3 ETFs
test_codes = ['510880', '159915', '513500']

print("=" * 60)
print("  AKShare Data Range Test")
print("=" * 60)

for code in test_codes:
    test_download(code)
    print()

print("=" * 60)
print("Test complete")
print("=" * 60)
