#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案B v3: 基于周线数据，标记并跳过不完整周（<3个交易日的假期周）
对比：v4.3基准（所有周） vs 方案B（仅完整周）
"""
import sys, json, os, glob, statistics
from datetime import datetime, timedelta
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

MA_S, MA_L, LB, MAX_DEV, TOP_N = 5, 21, 3, 10, 2
INIT_CAPITAL = 1_000_000

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def load_history(code):
    for pat in [code, f'sh{code}', f'sz{code}']:
        matches = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if matches:
            try:
                with open(matches[0], 'r', encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null').replace('Infinity', '0')
                d = json.loads(raw)
                recs = d if isinstance(d, list) else d.get('records', d.get('data', []))
                return recs
            except:
                continue
    return None

def get_chinese_holiday_weeks():
    """返回2010-2026年A股休市导致不满5天的周（ISO周号）"""
    # 中国A股主要假期：春节(1-2月)、清明(4月)、劳动节(5月)、端午(6月)、中秋(9月)、国庆(10月)
    # 精确需要查日历，这里用已知数据
    # 格式：(year, week_num) 其中ISO周号
    holiday_weeks = set()
    
    # 2010-2026主要长假周（春节至少休3天以上的周，国庆休3天以上的周）
    # 这里先统计，后面用实际交易数据验证
    return holiday_weeks

def infer_trading_days_per_week(code, weekly_data):
    """
    从周线数据推断每周有多少个交易日
    方法：对比相邻周的时间间隔和收盘价变化
    更精确：直接用多只ETF的周线日期集合来推算
    """
    # 这个函数不需要了，改用下面更精确的方法
    pass

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--ma-s', type=int, default=MA_S)
    ap.add_argument('--ma-l', type=int, default=MA_L)
    ap.add_argument('--lb', type=int, default=LB)
    ap.add_argument('--max-dev', type=float, default=MAX_DEV)
    ap.add_argument('--top-n', type=int, default=TOP_N)
    ap.add_argument('--start', type=str, default='2010-W01')
    ap.add_argument('--end', type=str, default='2026-W24')
    ap.add_argument('--min-trading-days', type=int, default=3,
                   help='最少交易日数，少于此数的周被跳过')
    ap.add_argument('--output', type=str, default=None)
    args = ap.parse_args()

    label = f"Wk MA{args.ma_s}/{args.ma_l} LB{args.lb} D{args.max_dev} H{args.top_n} minTD={args.min_trading_days}"
    print(f"{'='*60}")
    print(f"  方案B v3: 跳过不完整周 (min_trading_days={args.min_trading_days})")
    print(f"  {label}")
    print(f"{'='*60}\n")

    # Load pool & data
    pool = load_pool()
    print(f"Loading {len(pool)} ETFs...")

    all_series = {}
    code_info = {}
    missing = 0

    for etf in pool:
        code = etf['code']
        recs = load_history(code)
        if recs and len(recs) >= args.ma_l + 5:
            series = []
            for r in recs:
                if isinstance(r, dict):
                    w = r.get('w', '')
                    close = r.get('close', 0)
                    date = r.get('date', '')
                else:
                    continue
                if close and close > 0 and w:
                    series.append({'w': w, 'close': float(close), 'date': date})
            if len(series) >= args.ma_l + 5:
                all_series[code] = series
                code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}
            else:
                missing += 1
        else:
            missing += 1

    print(f"  Loaded: {len(all_series)}/{len(pool)}, missing: {missing}")

    # === 关键：推断每周交易日数 ===
    # 方法：收集所有ETF的周线日期，用"该周最后一个交易日的日期"来推算
    # 如果一周正常5个交易日，最后交易日=周五
    # 如果只有1-3天（假期），最后交易日可能是周一~周四
    # 更精确：用"该周覆盖的日历日数"来推断
    
    all_weeks = {}  # week_str -> set of dates across all ETFs
    for code, series in all_series.items():
        for r in series:
            w = r['w']
            date = r.get('date', '')
            if w not in all_weeks:
                all_weeks[w] = set()
            if date:
                all_weeks[w].add(date)
    
    # 用日历推算每周交易日数
    # 方法：找出该周内所有ETF都有数据的日期范围
    # 更简单：用中国交易日历（周末+假期）
    # 最简单：用"该周最后一个交易日是周几"来推断
    # 如果周五有交易 -> 5天（大概率）
    # 如果周一~周四有交易 -> 可能<5天
    
    # 实际上最精确的方法：统计所有周线日期
    # 周线date是该周最后一个交易日
    # 如果date是周五 -> 5天
    # 如果date是周四 -> 4天（如国庆前）
    # 如果date是周三 -> 3天（如春节）
    
    import calendar
    week_trading_days = {}  # week_str -> estimated trading days
    
    for w, dates in all_weeks.items():
        if not dates:
            continue
        # 取最晚的日期作为该周最后交易日
        last_date_str = max(dates)
        try:
            last_dt = datetime.strptime(last_date_str, '%Y-%m-%d')
        except:
            continue
        
        # 简单推算：周五=5天, 周四=4天, 周三=3天, 周二=2天, 周一=1天
        weekday = last_dt.weekday()  # 0=Monday, 4=Friday
        estimated_td = weekday + 1  # 粗略估算
        
        # 更精确：考虑调休（周六上班）
        # 如果最后一个交易日是周五，就是5天
        # 如果是周四，可能是4天（假期）或5天（周五休市补周四）
        # 对于A股，最常见的不完整周模式：
        # - 春节前/后：连续休市3-7天，最后交易日可能提前到周四
        # - 国庆前：9月30日休市，最后一交易日可能是周三或周四
        # - 劳动节：休3天，可能周一/周二休市
        
        week_trading_days[w] = estimated_td

    # 统计不完整周
    incomplete_weeks = {w: td for w, td in week_trading_days.items() if td < args.min_trading_days}
    complete_weeks = {w: td for w, td in week_trading_days.items() if td >= args.min_trading_days}
    
    print(f"\n  Total weeks: {len(week_trading_days)}")
    print(f"  Complete weeks (>= {args.min_trading_days} days): {len(complete_weeks)}")
    print(f"  Incomplete weeks (< {args.min_trading_days} days): {len(incomplete_weeks)}")
    
    if incomplete_weeks:
        print(f"\n  Incomplete weeks sample:")
        for w in sorted(incomplete_weeks.keys())[:20]:
            print(f"    {w}: ~{incomplete_weeks[w]} trading days")
    
    # Run two backtests: with and without incomplete weeks
    for mode, skip_weeks in [("BASELINE (all weeks)", set()), 
                              (f"FILTERED (skip <{args.min_trading_days}d weeks)", set(incomplete_weeks.keys()))]:
        print(f"\n{'='*60}")
        print(f"  Running: {mode}")
        print(f"  Skipping {len(skip_weeks)} weeks")
        print(f"{'='*60}")
        
        portfolio = {}
        cash = INIT_CAPITAL
        eq_curve = []
        trades = []
        n_buys = n_sells = 0
        skipped = 0

        # Get sorted weeks
        all_week_keys = sorted(set().union(*[set(r['w'] for r in s) for s in all_series.values()]))
        all_week_keys = [w for w in all_week_keys if w >= args.start and w <= args.end]

        for wi, week in enumerate(all_week_keys):
            # Skip incomplete weeks
            if week in skip_weeks:
                # 不调仓，沿用上周持仓
                skipped += 1
                # 仍需记录equity（用本周收盘价）
                equity = cash
                for code, pos in portfolio.items():
                    # 找本周收盘价
                    for r in reversed(all_series.get(code, [])):
                        if r['w'] == week:
                            equity += pos['weight'] * r['close']
                            break
                    else:
                        equity += pos['weight'] * pos['buy_price']
                
                eq_curve.append({'date': week, 'eq': equity, 'nh': len(portfolio),
                               'holds': [code_info.get(c, {}).get('name', c) for c in portfolio],
                               'skipped': True})
                continue

            # Signal calculation (same as v4.3)
            candidates = []
            for code, series in all_series.items():
                # Find data up to this week
                wk_data = [r for r in series if r['w'] <= week]
                if len(wk_data) < args.ma_l + 1:
                    continue
                
                closes = [r['close'] for r in wk_data]
                n = len(closes)
                price = closes[-1]
                ma_s = sum(closes[-args.ma_s:]) / args.ma_s
                ma_l = sum(closes[-args.ma_l:]) / args.ma_l
                mom = closes[-1] / closes[-args.lb] - 1 if n > args.lb else None
                dev = price / ma_l - 1
                
                if mom is None or mom <= 0: continue
                if not (price > ma_s > ma_l): continue
                if dev > args.max_dev / 100.0: continue
                
                # G3 filter
                if len(closes) >= 2:
                    if closes[-1] / closes[-2] - 1 < -0.01: continue
                if len(closes) >= 4:
                    if closes[-1] / closes[-4] - 1 < 0: continue
                
                candidates.append({'code': code, 'close': price, 'mom': mom, 'dev': dev})
            
            candidates.sort(key=lambda x: x['mom'], reverse=True)
            
            # Category dedup
            cats = set()
            target = []
            for c in candidates:
                cat = code_info.get(c['code'], {}).get('cat', '') or c['code']
                if cat not in cats:
                    cats.add(cat)
                    target.append(c)
            target = target[:args.top_n]
            target_codes = {t['code'] for t in target}
            
            # Get next week's close for execution price (offset=1)
            # Find next week key
            next_week = None
            for nw in all_week_keys[wi+1:]:
                if nw not in skip_weeks:
                    next_week = nw
                    break
            
            if next_week is None and wi < len(all_week_keys) - 1:
                # Use current week close as fallback (no lookahead)
                next_week = week
            
            # Update HWM
            for code, pos in portfolio.items():
                for r in reversed(all_series.get(code, [])):
                    if r['w'] == next_week or r['w'] == week:
                        if r['close'] > pos['hwm']:
                            portfolio[code]['hwm'] = r['close']
                        break
            
            # Execution prices
            def get_exec_close(code, week_key):
                for r in reversed(all_series.get(code, [])):
                    if r['w'] == week_key:
                        return r['close']
                return None
            
            # Sells
            to_sell = []
            for code, pos in list(portfolio.items()):
                p = get_exec_close(code, next_week)
                if p is None:
                    to_sell.append((code, 'no_data')); continue
                cost_pnl = p / pos['buy_price'] - 1
                hwm_pnl = p / pos['hwm'] - 1
                if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                    to_sell.append((code, 'stop'))
                elif code not in target_codes:
                    to_sell.append((code, 'rebalance'))
            
            for code, reason in to_sell:
                pos = portfolio.pop(code)
                p = get_exec_close(code, next_week) or pos['buy_price']
                cash += pos['weight'] * p
                pnl = (p / pos['buy_price'] - 1) * 100
                trades.append({'week': next_week, 'act': 'S', 'code': code,
                              'name': code_info.get(code, {}).get('name', ''),
                              'pnl': round(pnl, 2), 'reason': reason})
                n_sells += 1
            
            # Equity after sells
            equity = cash + sum(pos['weight'] * (get_exec_close(c, next_week) or pos['buy_price'])
                              for c, pos in portfolio.items())
            
            # Buys
            slots = args.top_n - len(portfolio)
            if slots > 0 and equity > 0:
                buy_list = [t for t in target if t['code'] not in portfolio]
                slot_val = equity / args.top_n
                for bc in buy_list[:slots]:
                    exec_price = get_exec_close(bc['code'], next_week)
                    if exec_price is None or exec_price <= 0:
                        continue
                    weight = slot_val / exec_price
                    cost = weight * exec_price
                    if cost > cash * 0.98:
                        weight = cash * 0.98 / exec_price
                        cost = weight * exec_price
                    if weight <= 0: break
                    cash -= cost
                    portfolio[bc['code']] = {'weight': weight, 'buy_price': exec_price, 'hwm': exec_price}
                    trades.append({'week': next_week, 'act': 'B', 'code': bc['code'],
                                  'name': code_info.get(bc['code'], {}).get('name', ''),
                                  'price': round(exec_price, 4)})
                    n_buys += 1
            
            # Record equity
            equity = cash + sum(pos['weight'] * (get_exec_close(c, next_week) or pos['buy_price'])
                              for c, pos in portfolio.items())
            eq_curve.append({'date': next_week, 'eq': equity, 'nh': len(portfolio),
                           'holds': [code_info.get(c, {}).get('name', c) for c in portfolio],
                           'skipped': False})
        
        # Stats
        eqs = [e['eq'] for e in eq_curve]
        n = len(eqs)
        if n < 2:
            print("  Not enough data"); continue
        
        init, final = eqs[0], eqs[-1]
        total_ret = (final / init - 1) * 100
        ann_ret = ((final / init) ** (52 / max(n, 1)) - 1) * 100
        
        peak = eqs[0]
        max_dd = 0
        for eq in eqs:
            if eq > peak: peak = eq
            dd = eq / peak - 1
            if dd < max_dd: max_dd = dd
        
        d_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
        if d_rets:
            avg_r = statistics.mean(d_rets)
            std_r = statistics.stdev(d_rets) if len(d_rets) > 1 else 1e-9
            sharpe = (avg_r * 52 - 0.02) / (std_r * 52**0.5)
            win_rate = sum(1 for r in d_rets if r > 0) / len(d_rets) * 100
        else:
            sharpe = win_rate = 0
        
        print(f"\n  {mode}:")
        print(f"  Weeks: {n} (skipped {skipped})")
        print(f"  Total Ret:  {total_ret:+.1f}%")
        print(f"  Annual:     {ann_ret:+.1f}%")
        print(f"  Max DD:     {max_dd*100:.1f}%")
        print(f"  Sharpe:     {sharpe:.2f}")
        print(f"  Win Rate:   {win_rate:.1f}%")
        print(f"  Trades:     {n_buys}B / {n_sells}S")
        
        # Yearly
        print(f"\n  {'Year':<6} {'Ret':>8} {'DD':>8}")
        print(f"  {'-'*25}")
        yg = defaultdict(list)
        for e in eq_curve:
            yr = (e.get('date') or '')[:4]
            if not yr: continue
            yg[yr].append(e)
        for yr in sorted(yg):
            es = [e['eq'] for e in yg[yr]]
            if es[0] <= 0: continue
            ret = (es[-1] / es[0] - 1) * 100
            pk = es[0]
            yearly_max_dd = 0
            for eq in es:
                if eq > pk: pk = eq
                dd = (eq / pk - 1) * 100
                if dd < yearly_max_dd: yearly_max_dd = dd
            print(f"  {yr:<6} {ret:>+7.1f}% {yearly_max_dd:>7.1f}%")

if __name__ == '__main__':
    main()