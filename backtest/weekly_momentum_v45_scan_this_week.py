#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周线动量策略 v4.5 — 本周扫描
用法: python weekly_momentum_v45_scan_this_week.py
输出: weekly_momentum_v45_this_week.json + _results.txt (UTF-8)
"""
import json, glob, os, sys
from datetime import datetime

# 修复Windows控制台编码问题
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── 路径 ──────────────────────────────────────────────────────────────
HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

# ── 策略参数（对齐 weekly_scan_v4.py） ──────────────────────────────
WARMUP_WEEKS  = 21
WEIGHT_MOM1W  = 0.40
WEIGHT_MOM3W  = 0.40
WEIGHT_MOM8W  = 0.20
MIN_MOM_SCORE = 0.0
MAX_OFF_MA5   = 0.15
ATR_RATIO_LOW = 0.85
HOLD_N        = 3
STOP1_PCT     = -0.08   # 成本 -8%
STOP2_PCT     = -0.10   # 高点回撤 -10%

# ── ATR 容差（对齐原脚本 DEFAULT_LB=3） ───────────────────────────
ATR_LOOKBACK  = 3
ATR_TOLERANCE = 3

# ───────────────────────────────────────────────────────────────────────
def load_etf_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return d.get('data', d.get('etfs', []))

def load_history(code):
    for pat in [f'{code}.json', f'sh{code}.json', f'sz{code}.json', f'bj{code}.json']:
        fp = os.path.join(HISTORY_DIR, pat)
        if os.path.exists(fp):
            with open(fp, 'r', encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', [])
    return []

def calc_indicators(records):
    if len(records) < WARMUP_WEEKS + 2:
        return []
    close_arr = [r['close'] for r in records]
    high_arr  = [r['high'] for r in records]
    low_arr   = [r['low'] for r in records]
    vol_arr   = [r.get('vol', 0) for r in records]
    week_arr  = [r['w'] for r in records]

    results = []
    for i in range(WARMUP_WEEKS, len(records)):
        w = week_arr[i]
        c = close_arr[i]

        ma5  = sum(close_arr[i-5:i]) / 5
        ma21 = sum(close_arr[i-21:i]) / 21

        mom1w = close_arr[i] / close_arr[i-1] - 1 if i-1 >= 0 else None
        mom3w = close_arr[i] / close_arr[i-3] - 1 if i-3 >= 0 else None
        mom8w = close_arr[i] / close_arr[i-7] - 1 if i-7 >= 0 else None

        score = 0
        if mom1w is not None: score += WEIGHT_MOM1W * mom1w
        if mom3w is not None: score += WEIGHT_MOM3W * mom3w
        if mom8w is not None: score += WEIGHT_MOM8W * mom8w

        off_ma5 = (c - ma5) / ma5 if ma5 > 0 else 0

        def calc_atr(st, en):
            trs = []
            for j in range(max(1, st), min(en, len(records))):
                h = high_arr[j]
                l = low_arr[j]
                pc = close_arr[j-1]
                tr = max(h - l, abs(h - pc), abs(l - pc))
                trs.append(tr)
            return sum(trs) / len(trs) if trs else 0

        atr14 = calc_atr(i-13, i+1)
        atr21 = calc_atr(i-20, i+1)
        atr_ratio = atr14 / atr21 if atr21 > 0 else 0
        vol_avg = sum(vol_arr[max(0,i-3):i+1]) / min(4, i+1)

        results.append({
            'w': week_arr[i],
            'idx': i,
            'score': score,
            'mom1w': mom1w,
            'mom3w': mom3w,
            'mom8w': mom8w,
            'close': c,
            'ma5': ma5,
            'ma21': ma21,
            'off_ma5': off_ma5,
            'atr14': atr14,
            'atr21': atr21,
            'atr_ratio': atr_ratio,
            'volume': vol_avg,
        })
    return results

def check_signal(ind):
    if ind['score'] <= MIN_MOM_SCORE:
        return False, 'score_too_low'
    if not (ind['close'] > ind['ma5'] and ind['ma5'] > ind['ma21']):
        return False, 'trend_down'
    if ind['off_ma5'] > MAX_OFF_MA5:
        return False, 'off_ma5_too_high'
    if ind['atr_ratio'] < ATR_RATIO_LOW:
        return False, 'atr_ratio_too_low'
    return True, 'pass'

def safe_print(*args, **kwargs):
    """Print to console, ignoring encoding errors"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: replace non-ASCII with ?
        s = ' '.join(str(a) for a in args)
        s_ascii = s.encode('ascii', errors='replace').decode('ascii')
        print(s_ascii, **kwargs)

# ── 主逻辑 ───────────────────────────────────────────────────────────
def main():
    safe_print('=== 周线动量策略 v4.5 — 本周扫描 ===')
    safe_print()

    etfs = load_etf_pool()
    safe_print(f'ETF池: {len(etfs)} 只')

    all_indicators = {}
    latest_week = None
    load_count = 0
    fail_count = 0

    for etf in etfs:
        code = etf['code']
        name = etf.get('name', code)
        cat  = etf.get('category', '')
        records = load_history(code)
        if len(records) < WARMUP_WEEKS + 2:
            fail_count += 1
            continue
        inds = calc_indicators(records)
        if not inds:
            fail_count += 1
            continue
        all_indicators[code] = {
            'name': name,
            'category': cat,
            'indicators': inds,
        }
        w = inds[-1]['w']
        if latest_week is None or w > latest_week:
            latest_week = w
        load_count += 1

    safe_print(f'成功加载: {load_count} 只, 失败: {fail_count} 只')
    safe_print(f'最新数据周: {latest_week}')
    safe_print()

    if latest_week is None:
        safe_print('ERROR: 无可用数据')
        return

    scan_results = []
    for code, info in all_indicators.items():
        inds = info['indicators']
        ind = None
        for x in inds:
            if x['w'] == latest_week:
                ind = x
                break
        if ind is None:
            continue
        ok, reason = check_signal(ind)
        scan_results.append({
            'code': code,
            'name': info['name'],
            'category': info['category'],
            'pass': ok,
            'reason': reason,
            'score': ind['score'],
            'mom1w': ind['mom1w'],
            'mom3w': ind['mom3w'],
            'mom8w': ind['mom8w'],
            'close': ind['close'],
            'ma5': ind['ma5'],
            'ma21': ind['ma21'],
            'off_ma5': ind['off_ma5'],
            'atr_ratio': ind['atr_ratio'],
            'atr14': ind['atr14'],
            'atr21': ind['atr21'],
        })

    scan_results.sort(key=lambda x: x['score'], reverse=True)
    passed = [x for x in scan_results if x['pass']]
    failed = [x for x in scan_results if not x['pass']]
    fail_sorted = sorted(failed, key=lambda x: x['score'], reverse=True)

    safe_print(f'=== {latest_week} 扫描结果: 通过 {len(passed)} 只 / 未通过 {len(failed)} 只 ===')
    safe_print()

    # ── 写 UTF-8 结果文件 ─────────────────────────────────────────
    lines = []
    lines.append(f'=== 周线动量策略 v4.5 — {latest_week} 扫描结果 ===')
    lines.append(f'扫描时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'ETF池: {len(etfs)} 只, 成功加载: {load_count} 只')
    lines.append(f'通过过滤: {len(passed)} 只, 未通过: {len(failed)} 只')
    lines.append('')

    if passed:
        lines.append('=== 通过过滤的ETF（按评分排序）===')
        lines.append(f'{"排名":<6} {"代码":<10} {"名称":<24} {"评分%":>10} {"1周%":>8} {"3周%":>8} {"8周%":>8} {"收盘价":>8} {"MA5":>8} {"偏离%":>8} {"ATR比":>8} {"类别":<20}')
        lines.append('-' * 140)
        for i, x in enumerate(passed):
            lines.append(
                f'{i+1:<6} {x["code"]:<10} {x["name"]:<24} '
                f'{x["score"]*100:>9.2f}% {x["mom1w"]*100:>7.2f}% {x["mom3w"]*100:>7.2f}% {x["mom8w"]*100:>7.2f}% '
                f'{x["close"]:>8.3f} {x["ma5"]:>8.3f} {x["off_ma5"]*100:>7.1f}% {x["atr_ratio"]:>7.2f}  {x["category"]:<20}'
            )
        lines.append('')

        # 同类别去重，取前3
        lines.append('=== 推荐买入（同类别去重，评分前3只）===')
        selected = []
        seen_cats = set()
        for x in passed:
            cat = x['category'] or 'OTHER'
            if cat not in seen_cats:
                selected.append(x)
                seen_cats.add(cat)
            if len(selected) >= HOLD_N:
                break
        if len(selected) < HOLD_N:
            for x in passed:
                if x not in selected:
                    selected.append(x)
                if len(selected) >= HOLD_N:
                    break

        for i, x in enumerate(selected):
            lines.append(f'')
            lines.append(f'  [买入标的 {i+1}] {x["code"]} {x["name"]}  [{x["category"]}]')
            lines.append(f'  评分: {x["score"]*100:.2f}%  (1周:{x["mom1w"]*100:.2f}%  3周:{x["mom3w"]*100:.2f}%  8周:{x["mom8w"]*100:.2f}%)')
            lines.append(f'  价格: {x["close"]:.3f}  MA5:{x["ma5"]:.3f}  MA21:{x["ma21"]:.3f}  偏离:{x["off_ma5"]*100:.1f}%')
            lines.append(f'  ATR14:{x["atr14"]:.4f}  ATR21:{x["atr21"]:.4f}  比率:{x["atr_ratio"]:.2f}')
            lines.append(f'  止损线1 (成本-8%): {x["close"]*0.92:.3f}')
            lines.append(f'  止损线2 (高点回撤-10%): 需跟踪持仓期间最高价')
            lines.append(f'  执行: 本周五({latest_week})收盘后下单，下周一开盘价执行')
        lines.append('')

    if failed:
        lines.append('=== 未通过过滤（按评分降序，前20名）===')
        reason_map = {
            'score_too_low': '评分过低',
            'trend_down': '趋势向下(close<MA5或MA5<MA21)',
            'off_ma5_too_high': '均线偏离过高(>15%)',
            'atr_ratio_too_low': '波动率过低(ATR比率<0.85)',
        }
        lines.append(f'{"代码":<10} {"名称":<24} {"评分%":>10} {"失败原因":<30} {"偏离%":>8} {"ATR比":>8}')
        lines.append('-' * 110)
        for x in fail_sorted[:20]:
            r = reason_map.get(x['reason'], x['reason'])
            lines.append(f'{x["code"]:<10} {x["name"]:<24} {x["score"]*100:>9.2f}% {r:<30} {x["off_ma5"]*100:>7.1f}% {x["atr_ratio"]:>7.2f}')
        lines.append('')

    lines.append('')
    lines.append('⚠️ 以上为策略信号，不构成投资建议。投资有风险，决策需谨慎。')

    # 写入文件
    out_file = 'weekly_momentum_v45_this_week_results.txt'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    safe_print(f'结果已保存: {out_file}')

    # 保存 JSON
    json_file = 'weekly_momentum_v45_this_week.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'scan_week': latest_week,
            'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_etf': len(scan_results),
            'passed': len(passed),
            'recommended': [{'code': x['code'], 'name': x['name'], 'score': x['score'],
                            'close': x['close'], 'stop1': x['close']*0.92,
                            'category': x['category']} for x in selected] if passed else [],
            'all_passed': [{'code': x['code'], 'name': x['name'], 'score': x['score'],
                           'mom1w': x['mom1w'], 'mom3w': x['mom3w'], 'mom8w': x['mom8w'],
                           'close': x['close'], 'off_ma5': x['off_ma5'], 'atr_ratio': x['atr_ratio'],
                           'category': x['category']} for x in passed],
            'all_failed': [{'code': x['code'], 'name': x['name'], 'score': x['score'],
                           'reason': x['reason']} for x in fail_sorted],
        }, f, ensure_ascii=False, indent=2)
    safe_print(f'JSON已保存: {json_file}')

    # 控制台摘要
    safe_print()
    if passed:
        safe_print(f'>>> 本周({latest_week})推荐买入 {len(selected)} 只ETF:')
        for i, x in enumerate(selected):
            safe_print(f'    {i+1}. {x["code"]} {x["name"]}  评分={x["score"]*100:.2f}%  收盘价={x["close"]:.3f}')
    else:
        safe_print(f'>>> 本周({latest_week})无ETF通过过滤，建议空仓观望')

if __name__ == '__main__':
    main()
