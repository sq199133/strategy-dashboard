import json, os, pandas as pd

# 读第一个文件看结构
f = r'D:\QClaw_Trading\data\history\159915.json'
with open(f, 'r', encoding='utf-8') as fh:
    raw = json.load(fh)
print(f'类型: {type(raw)}')
if isinstance(raw, list):
    print(f'列表长度: {len(raw)}')
    if raw:
        print(f'第一个元素字段: {list(raw[0].keys())}')
elif isinstance(raw, dict):
    print(f'字段: {list(raw.keys())}')
    if 'data' in raw:
        print(f'data长度: {len(raw["data"])}')
        if raw['data']:
            print(f'data[0]字段: {list(raw["data"][0].keys())}')
