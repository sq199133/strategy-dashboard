#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, datetime, glob, os
sys.stdout.reconfigure(encoding='utf-8')
import akshare as ak

print("="*65)
print(f"  今日复盘  2026-07-20 (周一)")
print("="*65)

# 1. 今日收盘
targets = [('159837','生物科技ETF','sz'),('560080','中药ETF','sh'),
           ('510300','沪深300ETF','sh'),('159949','创业板50ETF','sz')]
for code, name, exc in targets:
    try:
        df = ak.fund_etf_hist_em(symbol=code, period='daily',
                                  start_date='20260718', end_date='20260720', adjust='')
        if not df.empty:
            rows = df[['日期','收盘','涨跌幅']].tail(3).values
            print(f"\n{name}({code}):")
            for r in rows:
                print(f"  {r[0]}  收盘={r[1]:.3f}  涨跌%={r[2]:+.2f}")
    except Exception as e:
        print(f"{name}({code}) 获取失败: {e}")

# 2. 检查本地持仓记录（金山文档read_kdocs_sheet.py输出）
print("\n" + "="*65)
print("  持仓记录（来自金山文档）")
print("="*65)
# 读取金山文档sheet原始JSON
doc_file = r'D:\Qclaw_Trading\read_kdocs_result.json'
if os.path.exists(doc_file):
    with open(doc_file, encoding='utf-8') as f:
        raw = f.read()
    print("金山文档原始记录（前500字）:", raw[:500])
