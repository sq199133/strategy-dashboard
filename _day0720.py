#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, datetime, glob, os, re, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

def get_daily(secid):
    """腾讯日K接口获取日线"""
    url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           f'?param={secid},day,,,10,qfq')
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode('utf-8'))
        data = d.get('data',{}).get(secid,{})
        klines = data.get('qfqday',[]) or data.get('day',[])
        return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in klines]
    except Exception as e:
        return f'ERR:{e}'

print("="*65)
print(f"  今日复盘  2026-07-20 (周一)")
print("="*65)

targets = [
    ('sz159837', '生物科技ETF(159837)'),
    ('sh560080', '中药ETF(560080)'),
    ('sh510300', '沪深300ETF(510300)'),
    ('sz159949', '创业板50ETF(159949)'),
]

print(f"\n{'名称':<20}{'07-17':>10}{'07-18':>10}{'07-19':>10}  {'07-20':>10}{'周一涨跌':>10}")
print("-"*65)
for secid, name in targets:
    k = get_daily(secid)
    if isinstance(k, str):
        print(f"{name:<20} {k}")
        continue
    # 找这几天的数据
    dates = {row[0]: row[1] for row in k}
    row_strs = []
    for dt_ in ['2026-07-17','2026-07-18','2026-07-20']:
        # 07-18是周六，07-19是周日，市场休市，显示--
        p = dates.get(dt_)
        row_strs.append(f"{p:.3f}" if p else "  --  ")
    p17 = dates.get('2026-07-17')
    p20 = dates.get('2026-07-20')
    chg = f"{(p20/p17-1)*100:+.2f}%" if p17 and p20 else ""
    print(f"{name:<20}{row_strs[0]:>10}{row_strs[1]:>10}{' -- ':>10}{row_strs[2]:>10}{chg:>10}")

# 3. 金山文档持仓检查
print("\n" + "="*65)
print("  持仓检查（金山文档最新记录）")
print("="*65)
try:
    import subprocess
    r = subprocess.run(['python', r'D:\Qclaw_Trading\read_kdocs_sheet.py'],
        capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace',
        cwd=r'D:\Qclaw_Trading')
    # 找159837和560080相关行
    lines = [l for l in r.stdout.split('\n') if '159837' in l or '560080' in l or '生物' in l or '中药' in l]
    for l in lines:
        print(l)
    if not lines:
        print("未找到159837/560080相关记录，显示最近5行：")
        for l in r.stdout.split('\n')[-5:]:
            if l.strip(): print(l)
except Exception as e:
    print(f"读取失败: {e}")
