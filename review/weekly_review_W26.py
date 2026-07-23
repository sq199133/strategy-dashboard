#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-W26 周度复盘"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')
sys.path.insert(0, '.')
import weekly_scan_v4 as ws

print(f'=== 2026-W26 复盘 ===')
print(f'时间：2026-06-20 (周六)')
print(f'参数：LB={ws.DEFAULT_LB}, max_dev={ws.DEFAULT_MAX_DEV}%, top_n={ws.DEFAULT_TOP_N}')
print(f'ATR ratio: {ws.ATR_RATIO}, Score: W1={ws.SCORE_W1} W3={ws.SCORE_W3} W8={1-ws.SCORE_W1-ws.SCORE_W3:.1f}')
print()

etfs = ws.load_pool()
pool_map = {e['code']: e.get('name', '') for e in etfs}
print(f'ETF池：{len(etfs)} 只')
print()

results = []
errors = []
error_detail = []

for i, e in enumerate(etfs):
    code = e['code']
    try:
        wk = ws.load_weekly_file(code)
        if wk is None:
            daily = ws.fetch_kline(code)
            if not daily:
                errors.append((code, 'no data'))
                continue
            wk = ws.agg_weekly(daily)
        wk = ws.filter_completed_weeks(wk)
        if len(wk) < 60:
            errors.append((code, f'short ({len(wk)}w)'))
            continue
        ni = ws.calc(wk)
        if ni is None or len(ni) == 0:
            errors.append((code, 'calc fail'))
            continue
        ind = ni[-1]
        score, detail = ws.check(ind, ws.DEFAULT_MAX_DEV)
        if score:
            results.append((code, ind))
    except Exception as ex:
        errors.append((code, f'{type(ex).__name__}: {ex}'))

results.sort(key=lambda r: r[1].get('score', r[1].get('mom', 0)), reverse=True)

print(f'合格：{len(results)} 只 / 跳过：{len(errors)} 只')
print()

# TOP 15
print(f'TOP 15 合格ETF：')
print(f"{'排名':<4} {'代码':<8} {'名称':<20} {'综合评分':>8} {'M3W':>8} {'M1W':>8} {'收盘':>8} {'MA5':>8} {'偏离':>6} {'ATR':>5}")
print(f"{'─'*90}")
for i, (code, r) in enumerate(results[:15]):
    name = pool_map.get(code, '')
    score = r.get('score', r.get('mom', 0))
    mom = r.get('mom', 0)  # M3W
    mom1w = r.get('mom1w', 0)
    close = r.get('close', 0)
    ma5 = r.get('ma5', 0)
    dev = r.get('dev', 0)
    atr = r.get('atr_ratio', -1)
    atr_s = f'{atr:.2f}' if atr is not None and atr >= 0 else 'N/A'
    print(f"{i+1:<4} {code:<8} {name:<20} {score:>+7.2%} {mom:>+7.2%} {mom1w:>+7.2%} {close:>7.3f} {ma5:>7.3f} {dev:>+5.2%} {atr_s:>5}")

# TOP 3 详细决策
print()
print(f'== TOP {ws.DEFAULT_TOP_N} 持仓决策 ==')
print(f"{'代码':<8} {'名称':<20} {'评分':>8} {'M1W':>8} {'M3W':>8} {'评分>0':>6} {'趋势':>6} {'偏离':>6} {'ATR':>5}")
print(f"{'─'*75}")
for code, r in results[:ws.DEFAULT_TOP_N]:
    name = pool_map.get(code, '')
    score = r.get('score', r.get('mom', 0))
    mom = r.get('mom', 0)
    mom1w = r.get('mom1w', 0)
    dev = r.get('dev', 0)
    atr = r.get('atr_ratio', -1)
    p = r['close']; a5 = r['ma5']; a21 = r['ma21']
    
    c1 = '✅' if score > 0 else '❌'
    c2 = '✅' if p > a5 > a21 else '❌'
    c3 = '✅' if abs(dev) <= ws.DEFAULT_MAX_DEV/100 else '❌'
    c4 = '✅' if (atr is None or atr >= ws.ATR_RATIO) else ('⏭️' if atr is None else '❌')
    print(f"{code:<8} {name:<20} {score:>+7.2%} {mom1w:>+7.2%} {mom:>+7.2%} {c1:>6} {c2:>6} {c3:>6} {c4:>5}")

# 当前持仓（从之前扫描结果推测）
print()
print('== 上周推测持仓 ==')
last_holds_code = ['159687', '588220', '562800']
for code in last_holds_code:
    name = pool_map.get(code, '')
    print(f'{code} {name}')

print()
print('== 本周建议调仓 ==')
for code, r in results[:ws.DEFAULT_TOP_N]:
    name = pool_map.get(code, '')
    print(f'  ✅ 买入 {code} {name}')

# 跳过统计
err_counts = {}
for c, msg in errors:
    key = msg[:30]
    err_counts[key] = err_counts.get(key, 0) + 1
print(f'\n跳过明细：')
for msg, cnt in sorted(err_counts.items(), key=lambda x: -x[1]):
    print(f'  {cnt:>3} 只: {msg}')
