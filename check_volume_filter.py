#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查合格ETF的成交量数据（模拟成交量过滤效果）
"""

import json, os, sys, glob, statistics
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'


def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))


def load_volume_data(code):
    """Load history with volume data."""
    for pat in [code, f'sh{code}', f'sz{code}']:
        matches = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}.json'))
        if matches:
            try:
                with open(matches[0], 'r', encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d = json.loads(raw)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl, vol = r.get('date', ''), float(r.get('close', 0)), int(r.get('vol', 0))
                    else:
                        ds, cl, vol = str(r[0]), float(r[2]), int(r[5]) if len(r) > 5 else int(r.get('vol', 0))
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        y, w, _ = dt.isocalendar()
                        week_key = f'{y}-W{w:02d}'
                        if week_key not in weeks:
                            weeks[week_key] = {'close': cl, 'volume': 0}
                        weeks[week_key]['close'] = cl
                        weeks[week_key]['volume'] += vol
                    except:
                        pass
                sw = sorted(weeks.items())
                return [(w, d['close'], d['volume']) for w, d in sw]
            except:
                continue
    return None


def main():
    pool = load_pool()
    print(f"检查 {len(pool)} 只ETF的成交量数据...\n")

    # 模拟扫描条件（v4.3参数）
    results = []

    for i, etf in enumerate(pool):
        code = etf['code']
        data = load_volume_data(code)
        if not data or len(data) < 25:
            continue

        # 检查最近一周的成交量 vs 过去20周平均成交量
        recent_volume = data[-1][2]
        ma20_volume = statistics.mean([v for w, c, v in data[-21:-1]]) if len(data) >= 21 else 0

        volume_ratio = recent_volume / ma20_volume if ma20_volume > 0 else 0

        # 简单的动量检查（模拟合格）
        if len(data) >= 4:
            mom = (data[-1][1] / data[-4][1] - 1) * 100  # 3周动量
            if mom > 0:  # 只看动量>0的
                results.append({
                    'code': code,
                    'name': etf.get('name', ''),
                    'momentum': round(mom, 2),
                    'volume_ratio': round(volume_ratio, 2),
                    'recent_volume': recent_volume,
                    'ma20_volume': int(ma20_volume)
                })

        if (i+1) % 50 == 0:
            print(f"  已处理 {i+1}/{len(pool)}...")

    # 排序：按动量降序
    results.sort(key=lambda x: x['momentum'], reverse=True)

    # 输出Top 10
    print(f"\n{'='*80}")
    print(f"动量>0的ETF成交量分析（Top 10）")
    print(f"{'='*80}\n")
    print(f"{'代码':<8} {'名称':<20} {'动量%':>8} {'量比':>6} {'本周量':>15} {'20周均量':>15}")
    print(f"{'-'*80}")

    for i, r in enumerate(results[:10], 1):
        print(f"{r['code']:<8} {r['name']:<20} {r['momentum']:>+7.1f}% {r['volume_ratio']:>5.2f}x {r['recent_volume']:>15,} {r['ma20_volume']:>15,}")

    # 统计成交量过滤的效果
    print(f"\n{'='*80}")
    print(f"成交量过滤模拟（阈值：量比>1.2）")
    print(f"{'='*80}\n")

    qualified_all = len(results)
    qualified_volume = len([r for r in results if r['volume_ratio'] > 1.2])

    print(f"动量>0的ETF总数：{qualified_all}")
    print(f"量比>1.2的ETF数量：{qualified_volume} ({qualified_volume/qualified_all*100:.1f}%)")
    print(f"预计过滤掉：{qualified_all - qualified_volume} 只ETF")

    # 看看Top 10中哪些会被过滤掉
    print(f"\nTop 10中成交量过滤结果：")
    for i, r in enumerate(results[:10], 1):
        status = "✓ 通过" if r['volume_ratio'] > 1.2 else "✗ 过滤"
        print(f"{i}. {r['code']} {r['name']} - 量比 {r['volume_ratio']:.2f}x {status}")


if __name__ == '__main__':
    main()
