# -*- coding: utf-8 -*-
import json

with open(r'D:\QClaw_Trading\data\etf_pool_V1_full.json', 'r', encoding='utf-8') as f:
    pool = json.load(f)

kw = ['沪深300', '中证500', '中证1000', '创业板', '科创板', '上证50', '深证成', '纳斯达克', '标普']
for item in pool['data']:
    idx = item.get('index', '')
    name = item.get('name', '')
    code = item.get('code', '')
    cat = item.get('category', '')
    if any(k in idx or k in name for k in kw):
        print(f'{code} | {name} | [{cat}] | {idx}')
