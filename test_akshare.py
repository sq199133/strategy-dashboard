#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test AKShare ETF data download"""

import akshare as ak
import pandas as pd

print("Testing AKShare ETF data download...")
print("=" * 60)

# Test different adjust parameters
test_codes = ['510880', '159915', '513500']
adjust_values = ['qfq', 'hfq', '']

for code in test_codes:
    print(f"\nTesting {code}:")
    
    for adjust in adjust_values:
        try:
            df = ak.fund_etf_hist_em(
                symbol=code,
                period='daily',
                start_date='20200101',
                end_date='20260613',
                adjust=adjust
            )
            
            if df is not None and not df.empty:
                print(f"  adjust='{adjust}': SUCCESS (shape={df.shape})")
                print(f"    Columns: {list(df.columns)}")
                print(f"    Date range: {df.iloc[0, 0]} ~ {df.iloc[-1, 0]}")
                break  # Use first successful adjust value
            else:
                print(f"  adjust='{adjust}': Empty data")
                
        except Exception as e:
            print(f"  adjust='{adjust}': Error - {e}")

print("\n" + "=" * 60)
print("Test complete")
