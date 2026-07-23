#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.2 weekly momentum scan (fixed version)
- 修复: 默认参数改为v4.2 (LB=5, max_dev=10, top_n=3)
- 新增: 沪深300市场状态过滤 (三周动量 > -1%)
- 修复: G3过滤动量计算 (使用wk[-4]而非wk[-3])
- 数据源: 使用本地历史文件 (与回测一致)

Usage: python weekly_scan_v4_fixed.py [--max-dev 10] [--top-n 3] [--holdings CODE1,CODE2,...]
"""

import json, os, sys, time, glob
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
OUTPUT_DIR = r'D:\QClaw_Trading\scan_results'
DEFAULT_MAX_DEV = 10  # v4.2: 10%
DEFAULT_TOP_N = 3     # v4.2: 3只
DEFAULT_LB = 5        # v4.2: LB=5
MA_S = 5
MA_L = 21


def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    etfs = data.get('data', data.get('etfs', []))
    print(f"Pool: {len(etfs)} ETFs")
    return etfs


def load_history_local(code):
    """Load history from local file (consistent with backtest)."""
    for pat in [code, f'sh{code}', f'sz{code}']:
        matches = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if matches:
            try:
                with open(matches[0], 'r', encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d = json.loads(raw)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r.get('date', ''), float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        y, w, _ = dt.isocalendar()
                        week_key = f'{y}-W{w:02d}'
                        # Keep latest close for the week
                        if week_key not in weeks or ds > weeks[week_key][0]:
                            weeks[week_key] = (ds, cl)
                    except:
                        pass
                # Return sorted list of (week, close)
                return sorted([(w, cl) for w, (ds, cl) in weeks.items()])
            except:
                continue
    return None


def load_hs300_momentum():
    """Load HS300 3-week momentum for market filter."""
    hs300 = load_history_local('000300')
    if not hs300 or len(hs300) < 5:
        return None
    
    weeks = [w for w, c in hs300]
    closes = [c for w, c in hs300]
    
    # Calculate 3-week momentum for each week
    mom_map = {}
    for i in range(5, len(closes)):  # Need at least 5 weeks for MA21
        w = weeks[i]
        mom = closes[i] / closes[i-5] - 1  # 3-week momentum (actually 4-week span)
        mom_map[w] = mom
    
    return mom_map


def calc_signals(weekly_data):
    """Calculate momentum signals for weekly data."""
    closes = [c for w, c in weekly_data]
    weeks = [w for w, c in weekly_data]
    n = len(closes)
    
    if n < MA_L + 1:
        return None
    
    out = []
    for i in range(MA_L, n):
        ma5 = sum(closes[i-MA_S+1:i+1]) / MA_S
        ma21 = sum(closes[i-MA_L+1:i+1]) / MA_L
        mom = (closes[i] / closes[i-DEFAULT_LB] - 1) if i >= DEFAULT_LB else None
        dev = closes[i] / ma21 - 1 if ma21 > 0 else None
        
        out.append({
            'week': weeks[i],
            'close': closes[i],
            'ma5': ma5,
            'ma21': ma21,
            'mom': mom,
            'dev': dev
        })
    
    return out


def check_conditions(ind, max_dev):
    """检查入场条件（不含G3过滤）"""
    if not ind:
        return False, {}
    
    m = ind['mom']
    p = ind['close']
    a5 = ind['ma5']
    a21 = ind['ma21']
    d = ind['dev']
    
    c1 = m is not None and m > 0
    c2 = p > a5 and a5 > a21
    c3 = d is not None and d <= max_dev / 100.0
    
    return c1 and c2 and c3, {'c1': c1, 'c2': c2, 'c3': c3}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-dev', type=float, default=DEFAULT_MAX_DEV)
    ap.add_argument('--top-n', type=int, default=DEFAULT_TOP_N)
    ap.add_argument('--lb', type=int, default=DEFAULT_LB)
    ap.add_argument('--holdings', type=str, default='')
    a = ap.parse_args()
    
    print(f"{'='*60}")
    print(f"  v4.2 Weekly Momentum Scan (Fixed)")
    print(f"  MA{MA_S}/{MA_L}, LB={a.lb}, dev<={a.max_dev}%, top={a.top_n}")
    print(f"  G3 filter: 3w>=0% AND 1w>=-1%")
    print(f"  Market filter: HS300 3w > -1%")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    etfs = load_pool()
    hs = set(a.holdings.split(',')) if a.holdings else set()
    
    # Load HS300 momentum for market filter
    hs300_mom = load_hs300_momentum()
    if hs300_mom:
        print(f"  HS300 momentum loaded: {len(hs300_mom)} weeks")
    else:
        print(f"  Warning: HS300 data not available, market filter disabled")
    
    results = []
    failed = 0
    
    for idx, etf in enumerate(etfs):
        code = etf['code']
        name = etf.get('name', code)
        
        pct = (idx + 1) / len(etfs) * 100
        sys.stdout.write(f'\r[{idx+1}/{len(etfs)}] {pct:.0f}% {code}     ')
        sys.stdout.flush()
        
        # Load from local file (consistent with backtest)
        weekly_data = load_history_local(code)
        if not weekly_data or len(weekly_data) < 30:
            failed += 1
            continue
        
        # Calculate signals
        ind = calc_signals(weekly_data)
        if not ind:
            failed += 1
            continue
        
        # Get latest week signal
        last = ind[-1]
        week = last['week']
        
        # Check basic conditions
        ok, cc = check_conditions(last, a.max_dev)
        
        # G3过滤：三周≥0% + 本周≥-1%
        g3_pass = True
        if len(weekly_data) >= 2:
            mom1w = weekly_data[-1][1] / weekly_data[-2][1] - 1
            if mom1w < -0.01:  # 本周涨幅 < -1%
                g3_pass = False
        
        if len(weekly_data) >= 4:  # FIXED: Need 4 weeks for 3-week momentum (wk[-4])
            mom3w = weekly_data[-1][1] / weekly_data[-4][1] - 1
            if mom3w < 0:  # 三周涨幅 < 0%
                g3_pass = False
        
        ok = ok and g3_pass
        
        # Market filter: HS300 3-week momentum > -1%
        market_pass = True
        if hs300_mom and week in hs300_mom:
            if hs300_mom[week] <= -0.01:
                market_pass = False
        
        ok = ok and market_pass
        
        results.append({
            'code': code,
            'name': name,
            'cat': etf.get('category', ''),
            'close': last['close'],
            'ma5': last['ma5'],
            'ma21': last['ma21'],
            'mom': last['mom'],
            'dev': last['dev'],
            'date_end': week,
            'passed': ok,
            'c1': cc.get('c1'),
            'c2': cc.get('c2'),
            'c3': cc.get('c3'),
            'g3': g3_pass,
            'market': market_pass,
            'holding': code in hs,
            'n_weeks': len(weekly_data),
        })
    
    print(f'\rDone. OK={len(results)} FAIL={failed}                     ')
    
    # === Build target portfolio ===
    qual = sorted([r for r in results if r['passed']],
                  key=lambda x: x['mom'], reverse=True)
    
    # Category dedup
    cats = set()
    dedup = []
    for r in qual:
        c = r['cat'] or r['code']
        if c not in cats:
            cats.add(c)
            dedup.append(r)
    
    target = dedup[:a.top_n]
    
    # === Trade actions ===
    target_codes = {r['code'] for r in target}
    
    if hs:
        sell = [r for r in results if r['holding'] and r['code'] not in target_codes]
        buy = [r for r in target if not r['holding']]
        keep = [r for r in target if r['holding']]
    else:
        sell = []
        buy = target
        keep = []
    
    # === Output ===
    print(f"\n{'='*60}")
    print(f"  SCAN SUMMARY")
    print(f"{'='*60}")
    print(f"  Total: {len(etfs)} | OK: {len(results)} | Fail: {failed}")
    print(f"  Qualified: {len(qual)} | After dedup: {len(dedup)}")
    print(f"{'='*60}\n")
    
    # -- Target Portfolio --
    print(f"TARGET PORTFOLIO (Top {a.top_n}, equal weight):\n")
    print(f"{'#':>2} {'code':<8} {'name':<16} {'cat':<12} {'close':>7} "
          f"{'MA5':>7} {'MA21':>7} {'mom%':>7} {'dev%':>7} {'action'}")
    print('-' * 95)
    for i, r in enumerate(target):
        if r['holding']:
            action = 'HOLD'
        else:
            action = 'BUY'
        print(f"{i+1:>2} {r['code']:<8} {r['name']:<16} {r['cat']:<12} "
              f"{r['close']:>7.3f} {r['ma5']:>7.3f} {r['ma21']:>7.3f} "
              f"{r['mom']*100:>+6.1f}% {r['dev']*100:>6.1f}%  {action}")
    
    # -- Trade actions --
    print(f"\n{'='*60}")
    print(f"  TRADE ACTIONS")
    print(f"{'='*60}\n")
    
    if sell:
        print(f"SELL ({len(sell)}):")
        for r in sell:
            # Why selling?
            if not r['passed']:
                reasons = []
                if not r['c1']: reasons.append('mom<=0')
                if not r['c2']: reasons.append('trend_break')
                if not r['c3']: reasons.append(f"dev>{a.max_dev}%")
                if not r['g3']: reasons.append('G3_fail')
                if not r['market']: reasons.append('market_filter')
                why = ', '.join(reasons)
            else:
                # Passed conditions but not in topN (replaced by higher momentum)
                rank = next((i+1 for i, d in enumerate(dedup) if d['code']==r['code']), 99)
                why = f"rank #{rank} out of top {a.top_n}, replaced by higher momentum"
            print(f"  SELL {r['code']} {r['name']:<16} | {why}")
    
    if buy:
        print(f"\nBUY ({len(buy)}):")
        for r in buy:
            print(f"  BUY  {r['code']} {r['name']:<16} mom={r['mom']*100:+.1f}% dev={r['dev']*100:.1f}%")
    
    if not sell and not buy:
        print("  No trades needed. Current portfolio is optimal.")
    
    if not target and hs:
        print("\n  WARNING: No qualified picks. Consider liquidating all holdings.")
    
    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fp = os.path.join(OUTPUT_DIR, f'weekly_scan_v4_{ts}.json')
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump({
            'ts': datetime.now().isoformat(),
            'params': {
                'ma_s': MA_S, 'ma_l': MA_L, 'lb': a.lb,
                'max_dev': a.max_dev, 'top_n': a.top_n,
                'market_filter': 'HS300 3w > -1%'
            },
            'total': len(etfs),
            'ok': len(results),
            'fail': failed,
            'qual': len(qual),
            'dedup': len(dedup),
            'target': target,
            'sell': sell,
            'buy': buy,
            'keep': keep,
            'all': results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {fp}")


if __name__ == '__main__':
    main()
