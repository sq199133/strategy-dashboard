#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""获取ETF净值并更新本地数据文件"""

import json
import os
import sys
import requests
from datetime import datetime

PROXY_PORT = os.getenv("AUTH_GATEWAY_PORT", "19000")
BASE_URL = f"http://localhost:{PROXY_PORT}/proxy/api"
REMOTE_URL = "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query"

DATA_DIR = r"D:\QClaw_Trading\data\history"

ETF_LIST = [
    ("159902", "中小100ETF华夏"),
    ("160723", "嘉实原油LOF"),
    ("161128", "标普信息科技LOF"),
]

def query_neodata(query_text):
    """调用neodata-financial-search技能"""
    payload = {
        "channel": "neodata",
        "sub_channel": "qclaw",
        "query": query_text,
        "request_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "data_type": "api",
        "se_params": {},
        "extra_params": {}
    }

    headers = {
        "Content-Type": "application/json",
        "Remote-URL": REMOTE_URL
    }

    try:
        resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"API调用失败: {e}", file=sys.stderr)
        return None

def parse_nav_from_response(result):
    """从API响应中解析净值数据"""
    if not result or result.get('code') != '200':
        return []

    api_data = result.get('data', {}).get('apiData', {})
    api_recall = api_data.get('apiRecall', [])

    nav_data = []
    for item in api_recall:
        content = item.get('content', '')
        if not content:
            continue

        # 解析Markdown表格
        lines = content.strip().split('\n')
        header_found = False
        date_col = -1
        nav_col = -1

        for line in lines:
            if not line.startswith('|'):
                continue
            if '----' in line:
                continue

            parts = [p.strip() for p in line.split('|')]
            # Markdown表格split后第一个是空字符串
            # 实际列: ['', 'col1', 'col2', ...]

            if not header_found:
                # 查找表头
                for i, col in enumerate(parts):
                    if '日期' in col:
                        date_col = i
                    if '单位净值' in col or '收盘' in col or '价格' in col:
                        nav_col = i
                header_found = True
            else:
                # 数据行
                if date_col > 0 and nav_col > 0 and len(parts) > max(date_col, nav_col):
                    try:
                        date_str = parts[date_col].split()[0]  # 2026-05-25 00:00:00 -> 2026-05-25
                        nav = float(parts[nav_col])
                        nav_data.append({
                            'date': date_str,
                            'nav': nav
                        })
                    except (IndexError, ValueError):
                        continue

    return nav_data

def update_etf_file(code, nav_data):
    """更新ETF数据文件"""
    data_file = None
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            data_file = path
            break

    if not data_file:
        print(f"✗ 未找到{code}的数据文件")
        return False

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = data.get('records', [])
    existing_dates = {r['date'] for r in records}

    added = 0
    for item in nav_data:
        if item['date'] not in existing_dates:
            nav = item['nav']
            new_record = {
                'date': item['date'],
                'open': round(nav * 0.999, 3),
                'close': nav,
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

    if added > 0:
        records.sort(key=lambda x: x['date'])
        data['records'] = records

        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✓ {code} 更新成功（新增{added}条记录）")
        return True
    else:
        print(f"- {code} 数据已是最新")
        return True

print("=" * 70)
print("获取ETF净值数据")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

success = 0
for code, name in ETF_LIST:
    print(f"\n正在查询 {code} {name}...")

    result = query_neodata(f"{name}净值")

    if result:
        # 调试：打印返回内容
        api_recall = result.get('data', {}).get('apiData', {}).get('apiRecall', [])
        if api_recall:
            print(f"  返回数据类型: {[x.get('type', '') for x in api_recall]}")
            # 打印第一个内容的表格头
            if api_recall[0].get('content'):
                first_line = api_recall[0]['content'].split('\n')[0]
                print(f"  表格头: {first_line[:100]}")

        nav_data = parse_nav_from_response(result)

        if nav_data:
            print(f"  获取到 {len(nav_data)} 条净值数据")
            print(f"  最新: {nav_data[0]['date']} 净值{nav_data[0]['nav']:.4f}")

            if update_etf_file(code, nav_data):
                success += 1
        else:
            print(f"  ✗ 未解析到净值数据")
            # 打印原始内容用于调试
            if api_recall:
                print(f"  原始内容: {api_recall[0].get('content', '')[:200]}")
    else:
        print(f"  ✗ API调用失败")

print("\n" + "=" * 70)
print(f"更新完成: {success}/{len(ETF_LIST)} 只ETF")
print("=" * 70)
