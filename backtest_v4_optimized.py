#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.4 Optimized Backtest - Dynamic Position Sizing + Volume Filter
优化1: 动态仓位管理（按动量强度分配权重）
优化2: 成交量过滤（本周成交量 > 过去20周平均成交量 * 1.2）

Usage: python backtest_v4_optimized.py [--dynamic-weight] [--volume-filter]
"""

import json, os, sys, glob, statistics
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'


def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))


def load_history_with_volume(code):
    """Load history with weekly volume data."""
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
                        ds, cl, vol = r.get('date', ''), float(r.get('close', 0)), int(r.get('volume', 0))
                    else:
                        ds, cl, vol = str(r[0]), float(r[2]), int(r[5]) if len(r) > 5 else 0
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


def backtest(args):
    """Run backtest with optional optimizations."""
    
    pool = load_pool()
    all_weeks = set()
    price_map = {}
    volume_map = {}
    
    print(f"Loading {len(pool)} ETFs...")
    for i, etf in enumerate(pool):
        code = etf['code']
        data = load_history_with_volume(code)
        if not data or len(data) < 30:
            continue
        
        weeks = [w for w, c, v in data]
        closes = [c for w, c, v in data]
        volumes = [v for w, c, v in data]
        
        all_weeks.update(weeks)
        price_map[code] = dict(zip(weeks, closes))
        volume_map[code] = dict(zip(weeks, volumes))
        
        if (i+1) % 50 == 0:
            print(f"  Loaded {i+1}/{len(pool)}...")
    
    all_weeks = sorted(all_weeks)
    print(f"Data: {all_weeks[0]} ~ {all_weeks[-1]} ({len(all_weeks)} weeks)\n")
    
    # Find common weeks
    min_weeks = defaultdict(int)
    for code in price_map:
        for w in price_map[code]:
            min_weeks[w] += 1
    
    valid_weeks = [w for w in all_weeks if min_weeks[w] >= len(price_map) * 0.8]
    if args.start:
        valid_weeks = [w for w in valid_weeks if w >= args.start]
    if args.end:
        valid_weeks = [w for w in valid_weeks if w <= args.end]
    
    print(f"Valid weeks: {len(valid_weeks)} (from {valid_weeks[0] if valid_weeks else 'N/A'})\n")
    
    # Backtest loop
    equity = args.capital
    cash = equity
    portfolio = {}
    eq_curve = []
    n_buys = n_sells = 0
    
    for week_idx, week in enumerate(valid_weeks):
        # ... (rest of backtest logic will be added)
        pass
    
    print("Backtest complete!")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-dev', type=float, default=10)
    ap.add_argument('--top-n', type=int, default=2)
    ap.add_argument('--lb', type=int, default=3)
    ap.add_argument('--ma-s', type=int, default=5)
    ap.add_argument('--ma-l', type=int, default=21)
    ap.add_argument('--capital', type=float, default=1.0)
    ap.add_argument('--start', type=str, default='2010-W01')
    ap.add_argument('--end', type=str, default='2026-W23')
    ap.add_argument('--dynamic-weight', action='store_true', help='Enable dynamic position sizing')
    ap.add_argument('--volume-filter', action='store_true', help='Enable volume filter')
    args = ap.parse_args()
    
    backtest(args)
