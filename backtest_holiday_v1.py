#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.3 Holiday-Aware Weekly Momentum Backtest
基于 backtest_v4_fixed.py，加入假期周自动检测与跳过逻辑

假期周检测：每周交易量 < 20% 的滚动4周均量 → 视为假期周，跳过该周
- 假期周的价格数据不参与动量计算
- 假期周不产生交易信号（跳过）
- 效果：用"前1个正常周"替代"当周"计算动量，更准确

数据源: D:\QClaw_Trading\data\history_long\ (腾讯API前复权周线)
"""

import json, os, sys, glob, statistics
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
OUTPUT_DIR  = r'D:\QClaw_Trading\backtest_results'
HOLIDAY_VOL_RATIO = 0.20  # 交易量 < 20% 滚动均量 → 假期周


def load_history_with_holidays(code):
    """Load history from local file, also detect and tag holiday weeks.
    
    Returns:
        full_weeks: [(week, date, close, vol)] - all weeks (original)
        normal_weeks: [(week, date, close)] - non-holiday weeks only
        holiday_weeks: set of week keys that are holidays
    """
    for pat in [code, f'sh{code}', f'sz{code}']:
        matches = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}.json'))
        if matches:
            try:
                with open(matches[0], 'r', encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d = json.loads(raw)
                recs = d if isinstance(d, list) else d.get('records', [])
                
                # Load all weekly records
                weeks_raw = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds  = r.get('date', '')
                        cl  = float(r.get('close', 0))
                        vol = float(r.get('vol', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                        vol = float(r[5]) if len(r) > 5 else 0
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        y, wn, _ = dt.isocalendar()
                        week_key = f'{y}-W{wn:02d}'
                        # Keep latest close and sum volume for the week
                        if week_key not in weeks_raw:
                            weeks_raw[week_key] = (ds, cl, vol)
                        else:
                            old_ds, old_cl, old_vol = weeks_raw[week_key]
                            # Update if later date
                            if ds > old_ds:
                                weeks_raw[week_key] = (ds, cl, vol)
                            # Accumulate volume
                            weeks_raw[week_key] = (old_ds, old_cl, old_vol + vol)
                    except:
                        pass
                
                # Sort by week
                sorted_weeks = sorted(weeks_raw.items())
                full_weeks = [(w, ds, cl, vol) for w, (ds, cl, vol) in sorted_weeks]
                
                if len(full_weeks) < 10:
                    return None, None, None
                
                # Detect holiday weeks using rolling 4-week average volume
                holiday_weeks = set()
                closes_for_vol = [cl for _, _, cl, _ in full_weeks]
                vols_for_check = [max(vol, 1) for _, _, _, vol in full_weeks]  # avoid zero
                
                for i, (wk, ds, cl, vol) in enumerate(full_weeks):
                    # Rolling 4-week average (including current week)
                    start_i = max(0, i - 3)
                    avg_vol = statistics.mean(vols_for_vol[start_i:i+1])
                    # Skip if avg_vol is very small (thinly traded ETF)
                    if avg_vol > 1000 and vol < HOLIDAY_VOL_RATIO * avg_vol:
                        holiday_weeks.add(wk)
                
                # Build normal (non-holiday) weeks list
                normal_weeks = [(wk, ds, cl) for wk, ds, cl, _ in full_weeks
                                if wk not in holiday_weeks]
                
                return full_weeks, normal_weeks, holiday_weeks
            except Exception as e:
                return None, None, None
    return None, None, None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-dev', type=float, default=10)
    ap.add_argument('--top-n', type=int, default=2)
    ap.add_argument('--lb', type=int, default=3)
    ap.add_argument('--ma-s', type=int, default=5)
    ap.add_argument('--ma-l', type=int, default=21)
    ap.add_argument('--capital', type=float, default=1.0)
    ap.add_argument('--start', type=str, default='2010-W01')
    ap.add_argument('--end', type=str, default='2026-W24')
    ap.add_argument('--output', type=str, default=None)
    args = ap.parse_args()

    label = f"MA{args.ma_s}/{args.ma_l} LB{args.lb} D{args.max_dev} H{args.top_n} [Holiday-Aware]"
    print(f"{'='*60}")
    print(f"  v4.3 Holiday-Aware Backtest: {label}")
    print(f"  Range: {args.start} ~ {args.end}")
    print(f"{'='*60}\n")

    # Get ETF codes from history directory
    etf_codes = sorted([f.replace('.json','') for f in os.listdir(HISTORY_DIR) if f.endswith('.json')])
    print(f"  Found {len(etf_codes)} ETFs in {HISTORY_DIR}")

    # Load all ETF histories with holiday detection
    all_full     = {}
    all_normal   = {}
    all_holidays = {}
    code_info    = {}
    missing = 0

    print("Loading ETF data with holiday detection...")
    for code in etf_codes:
        full, normal, holidays = load_history_with_holidays(code)
        if normal and len(normal) >= 30:
            all_full[code]     = full
            all_normal[code]  = normal
            all_holidays[code] = holidays
            code_info[code]   = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}
        else:
            missing += 1

    print(f"  Loaded: {len(all_normal)}/{len(etf_codes)}, missing: {missing}")

    # Collect all normal weeks (union across all ETFs)
    all_normal_week_keys = set()
    for nw in all_normal.values():
        for wk, _, _ in nw:
            all_normal_week_keys.add(wk)
    
    # Filter to backtest range
    normal_weeks_sorted = sorted(
        wk for wk in all_normal_week_keys
        if args.start <= wk <= args.end
    )
    print(f"  Normal weeks: {len(normal_weeks_sorted)} ({normal_weeks_sorted[0]} ~ {normal_weeks_sorted[-1]})")
    
    # Count total holidays across all ETFs
    total_holidays = sum(len(h) for h in all_holidays.values())
    avg_holidays = total_holidays / len(all_holidays) if all_holidays else 0
    print(f"  Avg holiday weeks per ETF: {avg_holidays:.1f}")
    
    # Show holiday week distribution
    holiday_week_count = defaultdict(int)
    for hs in all_holidays.values():
        for h in hs:
            if args.start <= h <= args.end:
                holiday_week_count[h] += 1
    if holiday_week_count:
        sorted_h = sorted(holiday_week_count.items(), key=lambda x: x[1], reverse=True)
        print(f"  Most common holiday weeks (ETF count):")
        for h, cnt in sorted_h[:10]:
            print(f"    {h}: {cnt} ETFs")

    def closes_until_normal(code, week_exclusive):
        """Get close prices up to (but not including) week, in normal weeks only."""
        result = []
        for wk, ds, cl in all_normal.get(code, []):
            if wk >= week_exclusive:
                break
            result.append((wk, cl))
        return result

    def close_at_normal(code, week):
        """Get close at specific normal week."""
        for wk, ds, cl in all_normal.get(code, []):
            if wk == week:
                return cl
        return None

    # =====================================================================
    # Signal function (uses normal weeks only)
    # =====================================================================
    def get_signal(code, sig_week_normal):
        """Compute signal at a NORMAL week using normal-week close series."""
        cs = closes_until_normal(code, sig_week_normal)  # up to but not including sig_week
        # cs = [(wk, close), ...] in normal weeks only
        closes = [cl for _, cl in cs]
        n = len(closes)
        
        if n < args.ma_l + 1:
            return None
        
        price = closes[-1]
        ma_s  = sum(closes[-args.ma_s:]) / args.ma_s
        ma_l  = sum(closes[-args.ma_l:]) / args.ma_l
        
        # Momentum: LB non-holiday weeks back
        if n > args.lb:
            mom = closes[-1] / closes[-1 - args.lb] - 1
        else:
            return None
        
        dev = price / ma_l - 1
        
        if mom <= 0:
            return None
        if not (price > ma_s > ma_l):
            return None
        if dev > args.max_dev / 100.0:
            return None
        
        # G3 filter: 3 non-holiday weeks >= 0% AND 1 non-holiday week >= -1%
        g3_pass = True
        if n >= 2:
            mom1w = closes[-1] / closes[-2] - 1
            if mom1w < -0.01:
                g3_pass = False
        if n >= 4:
            mom3w = closes[-1] / closes[-4] - 1
            if mom3w < 0:
                g3_pass = False
        
        if not g3_pass:
            return None
        
        return {'code': code, 'close': price, 'mom': mom, 'dev': dev}

    # =====================================================================
    # Backtest loop (over normal weeks)
    # =====================================================================
    portfolio  = {}
    cash       = args.capital
    eq_curve   = []
    trades     = []
    n_buys = n_sells = 0

    for i in range(len(normal_weeks_sorted) - 1):
        sig_week = normal_weeks_sorted[i]
        exec_week = normal_weeks_sorted[i + 1]  # next normal week

        # === 1. Generate signals at sig_week ===
        candidates = []
        for code in all_normal:
            sig = get_signal(code, sig_week)
            if sig:
                candidates.append(sig)
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

        # === 2. Check stop losses at exec_week ===
        for code in list(portfolio.keys()):
            p = close_at_normal(code, exec_week)
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p

        to_sell = []
        for code, pos in list(portfolio.items()):
            p = close_at_normal(code, exec_week)
            if p is None:
                to_sell.append((code, 'no_data'))
                continue
            cost_pnl = p / pos['buy_price'] - 1
            hwm_pnl  = p / pos['hwm'] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, 'stop'))
            elif code not in target_codes:
                to_sell.append((code, 'rebalance'))

        for code, reason in to_sell:
            pos  = portfolio.pop(code)
            p    = close_at_normal(code, exec_week) or pos['buy_price']
            cash += pos['weight'] * p
            pnl  = (p / pos['buy_price'] - 1) * 100
            trades.append({'w': exec_week, 'act': 'S', 'code': code,
                          'pnl': round(pnl, 2), 'reason': reason})
            n_sells += 1

        # === 3. Equity after sells ===
        equity = cash + sum(
            pos['weight'] * (close_at_normal(c, exec_week) or pos['buy_price'])
            for c, pos in portfolio.items()
        )

        # === 4. Buys ===
        slots   = args.top_n - len(portfolio)
        buy_list = [t for t in target if t['code'] not in portfolio]
        if slots > 0 and equity > 0:
            slot_val = equity / args.top_n
            for bc in buy_list[:slots]:
                exec_price = close_at_normal(bc['code'], exec_week)
                if exec_price is None or exec_price <= 0:
                    continue
                weight = slot_val / exec_price
                cost   = weight * exec_price
                if cost > cash * 0.98:
                    weight = cash * 0.98 / exec_price
                    cost   = weight * exec_price
                if weight <= 0:
                    break
                cash -= cost
                portfolio[bc['code']] = {
                    'weight': weight, 'buy_price': exec_price, 'hwm': exec_price
                }
                trades.append({'w': exec_week, 'act': 'B', 'code': bc['code'],
                              'price': round(exec_price, 4)})
                n_buys += 1

        # === 5. Record equity ===
        equity = cash + sum(
            pos['weight'] * (close_at_normal(c, exec_week) or pos['buy_price'])
            for c, pos in portfolio.items()
        )
        eq_curve.append({
            'w': exec_week, 'eq': equity, 'nh': len(portfolio),
            'cash': round(cash, 4), 'holds': list(portfolio.keys())
        })

    # =====================================================================
    # Statistics
    # =====================================================================
    eqs = [e['eq'] for e in eq_curve]
    n   = len(eqs)
    if n < 2:
        print("Not enough data"); return

    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    years     = n / 52
    ann_ret   = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0

    peak, max_dd = eqs[0], 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq / peak - 1
        if dd < max_dd: max_dd = dd

    w_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
    if w_rets:
        avg_w  = statistics.mean(w_rets)
        std_w  = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52**0.5)
        calmar = ann_ret / abs(max_dd * 100) if max_dd else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = calmar = win_rate = 0

    print(f"\n{'='*60}")
    print(f"  RESULTS: {label}")
    print(f"{'='*60}\n")
    print(f"  Period:     {normal_weeks_sorted[0]} ~ {normal_weeks_sorted[-1]} ({n} normal weeks, {years:.1f}y)")
    print(f"  Total Ret:  {total_ret:+.1f}%")
    print(f"  Annual:     {ann_ret:+.1f}%")
    print(f"  Max DD:     {max_dd*100:.1f}%")
    print(f"  Sharpe:     {sharpe:.2f}")
    print(f"  Calmar:     {calmar:.2f}")
    print(f"  Win Rate:   {win_rate:.1f}%")
    print(f"  Trades:     {n_buys}B / {n_sells}S")

    # Yearly breakdown
    print(f"\n  {'Year':<6} {'Ret':>8} {'DD':>8} {'Hold%':>8}")
    print(f"  {'-'*34}")
    yg = defaultdict(list)
    for e in eq_curve:
        yg[e['w'][:4]].append(e)
    for yr in sorted(yg):
        es = [e['eq'] for e in yg[yr]]
        if not es or es[0] <= 0: continue
        ret = (es[-1] / es[0] - 1) * 100
        pk = es[0]; dd = 0.0
        for eq in es:
            if eq > pk: pk = eq
            d = eq / pk - 1
            if d < dd: dd = d
        hold_pct = statistics.mean([e['nh'] for e in yg[yr]]) / args.top_n * 100
        print(f"  {yr:<6} {ret:>+8.1f}% {dd*100:>8.1f}% {hold_pct:>8.0f}%")

    print(f"\n  {'Holiday Weeks Skipped:':<30} {n + len(normal_weeks_sorted) - 2} total weeks → {n} normal weeks")
    print()

    # Save result JSON
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(OUTPUT_DIR, f'bt_holiday_{ts}.json')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            'label': label, 'args': vars(args),
            'total_ret': round(total_ret, 2), 'ann_ret': round(ann_ret, 2),
            'max_dd': round(max_dd * 100, 2), 'sharpe': round(sharpe, 3),
            'calmar': round(calmar, 2), 'win_rate': round(win_rate, 1),
            'n_buys': n_buys, 'n_sells': n_sells,
            'n_normal_weeks': n, 'years': round(years, 1),
        }, f, ensure_ascii=False, indent=2)
    print(f"  Result saved: {out_file}")


if __name__ == '__main__':
    main()
