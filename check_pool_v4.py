#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查ETF池文件结构"""
import json, os

# 尝试不同路径
for path in [
    r'D:\QClaw_Trading\data\etf_pool_V1_full.json',
    r'D:\QClaw_Trading\etf_pool_V1_full.json',
    r'D:\QClaw_Trading\data\etf_pool.js'
]:
    if not os.path.exists(path):
        print(f'{path}: NOT FOUND')
        continue
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    print(f'{path}: {len(content)} bytes')
    print(content[:600])
    print('---')
