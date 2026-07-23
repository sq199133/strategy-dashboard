#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os

# 检查所有pool文件
for fname in os.listdir('D:/QClaw_Trading'):
    if 'pool' not in fname.lower():
        continue
    path = os.path.join('D:/QClaw_Trading', fname)
    if not os.path.isfile(path):
        continue
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    print(f'=== {fname} ({len(content)} bytes) ===')
    # Show first 500 chars
    print(content[:500])
    print()
