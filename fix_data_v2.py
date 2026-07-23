#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复数据文件：删除错误的净值记录，保留正确数据"""

import json
import os

DATA_DIR = r"D:\QClaw_Trading\data\history"

# 已知的错误值（来自净值解析错误）
BAD_VALUES = {
    '159902': [2.040, 1.6100],  # 净值错误插入
    '160723': [],  # 这次没插入错误的
    '161128': [0.520],  # 净值错误插入
}

for code in ['159902', '160723', '161128']:
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = data.get('records', [])
            original_count = len(records)
            
            # 找出正确的最后日期（2026-05-21之前的数据都是正确的）
            # 保留所有2026-05-21及之前的数据
            # 对于2026-05-22及之后，只保留从实时行情获取的数据
            cleaned = []
            for r in records:
                if r['date'] <= '2026-05-21':
                    cleaned.append(r)
                elif r['date'] == '2026-05-27' and r['close'] > 5.0:
                    # 保留今日实时行情（只保留合理值）
                    # 159902: 5.110, 161128: 6.979
                    if code == '159902' and abs(r['close'] - 5.110) < 0.1:
                        cleaned.append(r)
                    elif code == '161128' and abs(r['close'] - 6.979) < 0.1:
                        cleaned.append(r)
                    else:
                        pass  # 丢弃
                # 丢弃2026-05-22~05-26的错误净值记录
            
            removed = original_count - len(cleaned)
            if removed > 0:
                data['records'] = cleaned
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"✓ {code}: 删除{removed}条错误记录，保留{len(cleaned)}条")
            else:
                print(f"- {code}: 无需修复")
            
            # 打印最新3条
            for r in cleaned[-3:]:
                print(f"  {r['date']}: close={r['close']:.3f}")
            break
