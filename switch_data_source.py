#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Switch backtest data source to history_long/"""
import sys, os, json, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

hl_dir = r'D:\QClaw_Trading\data\history_long'
h_dir = r'D:\QClaw_Trading\data\history'

# Check 501312
hl_files = [f.replace('.json','') for f in os.listdir(hl_dir) if f.endswith('.json') and not f.startswith('_')]
h_files = [f.replace('.json','') for f in os.listdir(h_dir) if f.endswith('.json')]

print('history_long/ ETF count:', len(hl_files))
print('history/ JSON count:', len(h_files))
print('501312 in history_long:', '501312' in hl_files)
print('501312 in history/:', any('501312' in f for f in h_files))

# Update backtest_v4_fixed.py
bt_file = r'D:\QClaw_Trading\backtest_v4_fixed.py'
with open(bt_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the HISTORY_DIR line (line 30, 0-indexed = 29)
changed = False
for i in range(len(lines)):
    if "HISTORY_DIR = r'D:\\QClaw_Trading\\data\\history'" in lines[i] and 'history_long' not in lines[i]:
        old = lines[i].rstrip()
        lines[i] = "HISTORY_DIR = r'D:\\QClaw_Trading\\data\\history_long'  # ✅ 腾讯API前复权(195 ETF, 2007+)\n"
        print(f'Changed line {i+1}:')
        print(f'  OLD: {old}')
        print(f'  NEW: {lines[i].rstrip()}')
        changed = True
        break

if changed:
    with open(bt_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print('backtest_v4_fixed.py updated!')
else:
    print('No change needed (already pointing to history_long?)')
    
# Also update weekly_scan_v4.py if needed
scan_file = r'D:\QClaw_Trading\weekly_scan_v4.py'
if os.path.exists(scan_file):
    with open(scan_file, 'r', encoding='utf-8') as f:
        scan_lines = f.readlines()
    scan_changed = False
    for i in range(len(scan_lines)):
        if "HISTORY_DIR = r'D:\\QClaw_Trading\\data\\history'" in scan_lines[i] and 'history_long' not in scan_lines[i]:
            old = scan_lines[i].rstrip()
            scan_lines[i] = "HISTORY_DIR = r'D:\\QClaw_Trading\\data\\history_long'  # ✅ 腾讯API前复权(195 ETF, 2007+)\n"
            print(f'Scan changed line {i+1}: {old} -> {scan_lines[i].rstrip()}')
            scan_changed = True
    if scan_changed:
        with open(scan_file, 'w', encoding='utf-8') as f:
            f.writelines(scan_lines)
        print('weekly_scan_v4.py updated!')
    else:
        print('weekly_scan_v4.py: no change needed')
else:
    print('weekly_scan_v4.py not found')
