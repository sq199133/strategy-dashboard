#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, glob, re, os

# 找所有pool文件
for p in sorted(glob.glob(r'D:\QClaw_Trading\*pool*.json') + glob.glob(r'D:\QClaw_Trading\*pool*.js')):
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
    codes = set(re.findall(r'"(?:code|证券代码)"\s*:\s*"(\d+)"', content))
    if not codes:
        codes = set(re.findall(r'"(?:code|证券代码)"\s*:\s*(\d+)', content))
    print(f'{os.path.basename(p)}: {len(codes)} codes' + (f' e.g. {list(codes)[:3]}' if codes else ' - no codes found'))

# 检查已下载
downloaded = set(f.replace('.json','') for f in os.listdir(r'D:\QClaw_Trading\data\history_long_v2') if f.endswith('.json'))
print(f'\nAlready downloaded to history_long_v2: {len(downloaded)}')

# 检查pool v1 full
v1_path = r'D:\QClaw_Trading\etf_pool_V1_full.json'
if os.path.exists(v1_path):
    with open(v1_path, 'r', encoding='utf-8') as f:
        full = json.load(f)
    all_codes = [item['code'] for item in full]
    print(f'V1_full total: {len(all_codes)} codes')
    missing = [c for c in all_codes if c not in downloaded]
    print(f'Still need to download: {len(missing)}')
    print(f'Examples: {missing[:10]}')
