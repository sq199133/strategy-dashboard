#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os

# 检查 pool 文件结构
for fname in ['etf_pool_cn.json', 'etf_pool_V1_full.json']:
    path = os.path.join('D:/QClaw_Trading', fname)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f'=== {fname} ===')
        print(f'Type: {type(data).__name__}, Length: {len(data)}')
        if isinstance(data, list) and len(data) > 0:
            print(f'Keys: {list(data[0].keys())}')
            print(f'Sample: {json.dumps(data[0], ensure_ascii=False, indent=2)[:300]}')
            # Try to extract codes
            codes = []
            for item in data:
                for k in ['code', '证券代码', 'CODE', 'ts_code', 'symbol']:
                    if k in item:
                        v = item[k]
                        codes.append(str(v).replace('.SZ','').replace('.SH','').strip())
                        break
            print(f'Codes found: {len(codes)}')
            if codes:
                print(f'Sample codes: {codes[:5]}')
        print()
