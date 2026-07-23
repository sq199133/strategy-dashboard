#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch weekly_scan_v4.py to v4.6.2: add vol_ratio filter"""
import re

with open('weekly_scan_v4.py', 'r', encoding='utf-8') as f:
    content = f.read()

print(f'Original length: {len(content)}')

# Step 1: 加入VOL_RATIO_THRESH常量
marker1 = 'C_BONUS  = 0.02   # 仙人指路加分（v2回测最优：年化+14.40%）\nB1_BONUS = 0.00   # 红三兵加分（v2回0.03导致年化降至9.37%，已否决）'
insert1 = '\nVOL_RATIO_THRESH = 1.5  # 量比阈值：超过则跳过（高量能出货信号）v4.6.2'
if marker1 in content:
    idx1 = content.index(marker1) + len(marker1)
    content = content[:idx1] + insert1 + content[idx1:]
    print('Step 1 OK: added VOL_RATIO_THRESH')
else:
    print('Step 1 FAIL')

# Step 2: 在calc()里计算vol_ratio
marker2 = '        c_pattern = (\n            ci > oi and s2b > 1.0 and l_shadow < body * 0.5\n            and vol_r < 1.5 and ci > ma5 > ma21 and gain20w < 0.5\n        )'
insert2 = '\n        # v4.6.2: 计算量比\n        vol_ratio = vol_r if vol_r is not None else None'
if marker2 in content:
    idx2 = content.index(marker2) + len(marker2)
    content = content[:idx2] + insert2 + content[idx2:]
    print('Step 2 OK: added vol_ratio calculation')
else:
    print('Step 2 FAIL')

# Step 3: 在calc()返回值里加入vol_ratio
marker3 = "'c_pattern': c_pattern, 'b1_pattern': b1_ok}"
replace3 = "'c_pattern': c_pattern, 'b1_pattern': b1_ok, 'vol_ratio': vol_ratio}"
if marker3 in content:
    content = content.replace(marker3, replace3)
    print('Step 3 OK: added vol_ratio to calc() return')
else:
    print('Step 3 FAIL')

# Step 4: 在results里加入vol_ratio
marker4 = "'c_pattern': last.get('c_pattern'), 'b1_pattern': last.get('b1_pattern'),"
replace4 = "'c_pattern': last.get('c_pattern'), 'b1_pattern': last.get('b1_pattern'), 'vol_ratio': last.get('vol_ratio'),"
if marker4 in content:
    content = content.replace(marker4, replace4)
    print('Step 4 OK: added vol_ratio to results')
else:
    print('Step 4 FAIL')

# Step 5: 在评分前过滤高量能ETF
marker5 = '''    # v4.6: apply pattern bonus before sorting
    for r in results:
        if r['passed']:
            adj = r.get('score', r['mom'])
            if r.get('c_pattern'):  adj += C_BONUS   # +0.05仙人指路
            if r.get('b1_pattern'): adj += B1_BONUS  # +0.03红三兵
            r['_adj_score'] = adj'''
replace5 = '''    # v4.6.2: 过滤高量能ETF（量比>1.5为出货信号）
    skip_high_vol = 0
    for r in results:
        vr = r.get('vol_ratio')
        if vr is not None and vr > VOL_RATIO_THRESH:
            r['passed'] = False
            r['skip_reason'] = f'vol_ratio={vr:.2f}>1.5'
            skip_high_vol += 1
    if skip_high_vol > 0:
        print(f'  Skipped {skip_high_vol} high-volume ETFs (vol_ratio>1.5)')
    # v4.6: apply pattern bonus before sorting
    for r in results:
        if r['passed']:
            adj = r.get('score', r['mom'])
            if r.get('c_pattern'):  adj += C_BONUS   # +0.02仙人指路
            if r.get('b1_pattern'): adj += B1_BONUS  # +0.00红三兵
            r['_adj_score'] = adj'''
if marker5 in content:
    content = content.replace(marker5, replace5)
    print('Step 5 OK: added vol_ratio filtering')
else:
    print('Step 5 FAIL')

# Step 6: 更新版本号
old_ver = 'v4.6.1 weekly momentum scan  |  C(仙人指路)+0.02  B1(红三兵)已移除'
new_ver = 'v4.6.2 weekly momentum scan  |  C(仙人指路)+0.02  跳过量比>1.5'
if old_ver in content:
    content = content.replace(old_ver, new_ver)
    print('Step 6 OK: updated version to v4.6.2')
else:
    print('Step 6 FAIL: version string not found')

# 保存
with open('weekly_scan_v4.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Final length: {len(content)}')
print('Done!')
