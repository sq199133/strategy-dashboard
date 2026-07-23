#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF数据更新脚本 - 使用neodata API获取收盘价和净值"""

import json
import os
import sys
import uuid
import requests
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
PROXY_PORT = os.getenv("AUTH_GATEWAY_PORT", "19000")
BASE_URL = f"http://localhost:{PROXY_PORT}/proxy/api"
REMOTE_URL = "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query"

ETF_LIST = [
    ("159902", "中小100ETF华夏"),
    ("160723", "嘉实原油LOF"),
    ("161128", "标普信息科技LOF"),
]

def query_neodata(query_text):
    """调用neodata API"""
    payload = {
        "channel": "neodata",
        "sub_channel": "qclaw",
        "query": query_text,
        "request_id": uuid.uuid4().hex,
        "data_type": "api",
        "se_params": {},
        "extra_params": {}
    }
    headers = {
        "Content-Type": "application/json",
        "Remote-URL": REMOTE_URL
    }
    resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()

def parse_realtime_quote(result):
    """解析实时行情（收盘价）"""
    if not result or result.get('code') != '200':
        return None
    
    api_recall = result.get('data', {}).get('apiData', {}).get('apiRecall', [])
    for item in api_recall:
        if '实时' in item.get('type', '') or '行情' in item.get('type', ''):
            content = item.get('content', '')
            lines = content.strip().split('\n')
            for line in lines:
                if line.startswith('|') and '---' not in line:
                    parts = [p.strip() for p in line.split('|')]
                    # 实时行情表头: 市场类型 | 证券名称 | 证券代码 | 最新价格 | ...
                    # 数据行示例: | 深市 | 嘉实原油LOF | 160723 | 2.132 | ...
                    if len(parts) >= 5:
                        try:
                            code = parts[3].strip()
                            price = float(parts[4].strip())
                            if code and price > 0:
                                return {'price': price}
                        except (ValueError, IndexError):
                            continue
    return None

def parse_nav_history(result):
    """解析净值历史数据"""
    if not result or result.get('code') != '200':
        return []
    
    api_recall = result.get('data', {}).get('apiData', {}).get('apiRecall', [])
    nav_data = []
    
    for item in api_recall:
        if '净值' in item.get('type', ''):
            content = item.get('content', '')
            lines = content.strip().split('\n')
            
            # 解析表头找到列索引
            header_line = None
            data_lines = []
            for line in lines:
                if line.startswith('|') and '---' not in line:
                    if header_line is None:
                        header_line = line
                    else:
                        data_lines.append(line)
            
            if not header_line:
                continue
                
            header_parts = [p.strip() for p in header_line.split('|')]
            date_col = -1
            nav_col = -1
            
            for i, col in enumerate(header_parts):
                if '日期' in col:
                    date_col = i
                if '单位净值' in col:
                    nav_col = i
            
            if date_col < 0 or nav_col < 0:
                continue
            
            for line in data_lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) > max(date_col, nav_col):
                    try:
                        date_str = parts[date_col].split()[0]  # "2026-05-25 00:00:00" -> "2026-05-25"
                        nav = float(parts[nav_col])
                        if nav > 0:  # 过滤异常值
                            nav_data.append({'date': date_str, 'nav': nav})
                    except (ValueError, IndexError):
                        continue
    
    return nav_data

def update_etf_file(code, price_today, nav_data):
    """更新ETF数据文件"""
    data_file = None
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            data_file = path
            break
    
    if not data_file:
        print(f"  ✗ 未找到{code}的数据文件")
        return False
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = data.get('records', [])
    existing_dates = {r['date'] for r in records}
    
    added = 0
    
    # 1. 用净值数据补充历史（用于05-22~05-26等缺失日期）
    for item in nav_data:
        if item['date'] not in existing_dates:
            nav = item['nav']
            new_record = {
                'date': item['date'],
                'open': round(nav * 0.998, 3),
                'close': round(nav, 3),
                'high': round(nav * 1.005, 3),
                'low': round(nav * 0.995, 3),
                'vol': 0,
                'amount': 0,
                'change': 0,
                'change_pct': 0
            }
            records.append(new_record)
            existing_dates.add(item['date'])
            added += 1
    
    # 2. 用实时行情更新今日数据（优先级更高）
    if price_today and price_today > 0:
        today_str = datetime.now().strftime('%Y-%m-%d')
        # 如果今天已有记录，用实时价格覆盖
        found = False
        for r in records:
            if r['date'] == today_str:
                r['close'] = price_today
                r['high'] = max(r.get('high', price_today), price_today)
                r['low'] = min(r.get('low', price_today), price_today)
                found = True
                break
        if not found and today_str not in existing_dates:
            new_record = {
                'date': today_str,
                'open': round(price_today * 0.998, 3),
                'close': price_today,
                'high': round(price_today * 1.002, 3),
                'low': round(price_today * 0.998, 3),
                'vol': 0,
                'amount': 0,
                'change': 0,
                'change_pct': 0
            }
            records.append(new_record)
            existing_dates.add(today_str)
            added += 1
    
    if added > 0:
        records.sort(key=lambda x: x['date'])
        data['records'] = records
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 打印最新5条记录
    print(f"  最新数据:")
    for r in records[-3:]:
        print(f"    {r['date']}: close={r['close']:.3f}")
    
    return True

# ===== 主流程 =====
print("=" * 70)
print("ETF数据更新")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

success = 0
for code, name in ETF_LIST:
    print(f"\n--- {code} {name} ---")
    
    # 查询1: 实时行情（获取最新收盘价）
    print(f"  查询实时行情...")
    realtime_result = query_neodata(f"{code}{name}收盘价")
    realtime = parse_realtime_quote(realtime_result)
    if realtime:
        print(f"  ✓ 实时价格: {realtime['price']:.3f}")
    else:
        print(f"  - 实时行情未获取，尝试备用查询...")
        realtime_result2 = query_neodata(f"{code} {name}行情")
        realtime = parse_realtime_quote(realtime_result2)
        if realtime:
            print(f"  ✓ 实时价格(备用): {realtime['price']:.3f}")
        else:
            print(f"  ✗ 实时行情不可用")
    
    # 查询2: 净值历史（补充缺失日期）
    print(f"  查询净值历史...")
    nav_result = query_neodata(f"{name}净值")
    nav_data = parse_nav_history(nav_result)
    if nav_data:
        print(f"  ✓ 净值数据: {len(nav_data)}条, 最新 {nav_data[0]['date']} nav={nav_data[0]['nav']:.4f}")
    else:
        print(f"  - 净值历史不可用")
    
    # 更新文件
    price_today = realtime['price'] if realtime else None
    if update_etf_file(code, price_today, nav_data):
        success += 1

print("\n" + "=" * 70)
print(f"更新完成: {success}/{len(ETF_LIST)}")
print("=" * 70)
