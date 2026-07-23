#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v6.0 Dynamic LB Backtest: support fixed & hs300-based dynamic lookback periods
"""
import json, os, sys, glob, statistics
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'
POOL_FILE = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\Qclaw_Trading\backtest_results'

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def load_history(code):
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
                        ds, cl = r.get('date', ''), float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        y, w, _ = dt.isocalendar()
                        wk = f'{y}-W{w:02d}'
                        if wk not in weeks or ds > weeks[wk][0]:
                            weeks[wk] = (ds, cl)
                    except:
                        pass
                sw = sorted(weeks.items())
                return [(w, cl) for w, (ds, cl) in sw]
            except:
                continue
    return None

def load_hs300_weekly():
    path = r'D:\Qclaw_Trading\data\index_history\sh000300.json'
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read().replace('NaN', 'null')
    hd = json.loads(raw)
    recs = hd.get('records', [])
    weeks = {}
    for r in recs:
        ds, cl = r['date'], float(r['close'])
        dt = datetime.strptime(ds, '%Y-%m-%d')
        y, w, _ = dt.isocalendar()
        wk = f'{y}-W{w:02d}'
        if wk not in weeks or ds > weeks[wk][0]:
            weeks[wk] = (ds, cl)
    # Convert to {week: close} dict sorted
    return {wk: cl for wk, (ds, cl) in sorted(weeks.items())}

def compute_ma21(hs300_wk):
    """Precompute 21-week MA for HS300"""
    keys = sorted(hs300_wk.keys())
    ma21 = {}
    for i, wk in enumerate(keys):
        if i >= 20:
            vals = [hs300_wk[keys[j]] for j in range(i-20, i+1)]
            ma21[wk] = sum(vals) / len(vals)
    return ma21

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
    ap.add_argument('--end', type=str, default='2026-W25')
    ap.add_argument('--hs300-threshold', type=float, default=-100.0)
    ap.add_argument('--output', type=str, default=None)
    ap.add_argument('--qual-sizer', type=str, default='none')
    ap.add_argument('--mom1w-threshold', type=float, default=-1.0)
    ap.add_argument('--mom3w-threshold', type=float, default=0.0)
    ap.add_argument('--lb-mode', type=str, default='fixed', choices=['fixed', 'hs300'])
    ap.add_argument('--lb-trend', type=int, default=3, help='LB in trend market (HS300 > MA21)')
    ap.add_argument('--lb-choppy', type=int, default=2, help='LB in choppy market (HS300 <= MA21)')
    args = ap.parse_args()

    # Load HS300 if needed
    hs300_wk = {}
    hs300_ma21 = {}
    if args.lb_mode == 'hs300':
        print("Loading HS300 market state...")
        hs300_wk = load_hs300_weekly()
        hs300_ma21 = compute_ma21(hs300_wk)
        print(f"  HS300 weeks: {len(hs300_wk)}, MA21 computed")

    lb_label = f"LB{args.lb}" if args.lb_mode == 'fixed' else f"LB动态{args.lb_choppy}/{args.lb_trend}"
    g3_note = f" M1W{args.mom1w_threshold:+.0f}M3W{args.mom3w_threshold:+.0f}" if args.mom1w_threshold != -1 or args.mom3w_threshold != 0 else ''
    label = f"MA{args.ma_s}/{args.ma_l} {lb_label} D{args.max_dev} H{args.top_n}{g3_note}"
    sizer_note = f"+QS:{args.qual_sizer}" if args.qual_sizer != 'none' else ''
    print(f"{'='*60}")
    print(f"  v6.0 Dynamic LB Backtest: {label}{sizer_note}")
    print(f"  Range: {args.start} ~ {args.end}")
    print(f"{'='*60}\n")

    etfs = load_pool()
    print("Loading ETF history...")
    all_series = {}
    code_info = {}
    missing = 0
    for etf in etfs:
        code = etf['code']
        s = load_history(code)
        if s and len(s) >= 30:
            all_series[code] = s
            code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}
        else:
            missing += 1
    print(f"  Loaded: {len(all_series)}/{len(etfs)}, missing: {missing}")

    weeks_set = set()
    for s in all_series.values():
        for w, c in s:
            weeks_set.add(w)
    all_weeks = sorted(w for w in weeks_set if args.start <= w <= args.end)
    print(f"  Weeks: {len(all_weeks)} ({all_weeks[0]} ~ {all_weeks[-1]})\n")

    def closes_until(code, week):
        return [c for w, c in all_series.get(code, []) if w <= week]

    def close_at(code, week):
        for w, c in all_series.get(code, []):
            if w == week: return c
            if w > week: return None
        return None

    # Precompute available counts
    ma_l = args.ma_l
    first_avail = {}
    for code, series in all_series.items():
        first_avail[code] = series[ma_l][0] if len(series) >= ma_l + 1 else None
    available_counts = {}
    for w in all_weeks:
        available_counts[w] = sum(1 for c in first_avail if first_avail[c] is not None and first_avail[c] <= w)
    print(f"    Available ETFs: {min(available_counts.values())}~{max(available_counts.values())}")

    # Track LB usage
    lb_usage = defaultdict(int)

    portfolio = {}
    cash = args.capital
    eq_curve = []
    n_buys = n_sells = 0
    total_qual = []

    for i in range(len(all_weeks) - 1):
        sig_week = all_weeks[i]
        exec_week = all_weeks[i + 1]

        # Determine LB for this week
        if args.lb_mode == 'hs300':
            h_val = hs300_wk.get(sig_week)
            h_ma = hs300_ma21.get(sig_week)
            if h_val is not None and h_ma is not None:
                current_lb = args.lb_trend if h_val > h_ma else args.lb_choppy
            else:
                current_lb = args.lb  # fallback
        else:
            current_lb = args.lb
        lb_usage[current_lb] += 1

        # Generate signals with current_lb
        candidates = []
        for code in all_series:
            cs = closes_until(code, sig_week)
            n = len(cs)
            if n < ma_l + 1:
                continue
            price = cs[-1]
            ma_s_val = sum(cs[-args.ma_s:]) / args.ma_s
            ma_l_val = sum(cs[-args.ma_l:]) / args.ma_l
            mom = cs[-1] / cs[-current_lb] - 1 if n > current_lb else None
            dev = price / ma_l_val - 1
            if mom is None or mom <= 0:
                continue
            if not (price > ma_s_val > ma_l_val):
                continue
            if dev > args.max_dev / 100.0:
                continue
            # G3 filter
            if len(cs) >= 2:
                mom1w = cs[-1] / cs[-2] - 1
                if mom1w < args.mom1w_threshold / 100.0:
                    continue
            if len(cs) >= 4:
                mom3w = cs[-1] / cs[-4] - 1
                if mom3w < args.mom3w_threshold / 100.0:
                    continue
            candidates.append({'code': code, 'close': price, 'mom': mom, 'dev': dev})

        n_qualified = len(candidates)
        total_qual.append(n_qualified)
        n_available = available_counts.get(sig_week, 1)

        # Size factor (same compute_size_factor function)
        def size_factor(nq, na, cfg):
            if cfg == 'none' or cfg is None: return 1.0
            parts = cfg.split(':')
            mode = parts[0]
            if mode == 'step':
                return float(parts[2]) if nq < int(parts[1]) else 1.0
            elif mode == 'steppct':
                ratio = nq / max(1, na)
                return float(parts[2]) if ratio < float(parts[1]) else 1.0
            else:
                return 1.0
        sf = size_factor(n_qualified, n_available, args.qual_sizer)

        # Dedup & pick top N
        candidates.sort(key=lambda x: x['mom'], reverse=True)
        cats = set()
        target = []
        for c in candidates:
            cat = code_info.get(c['code'], {}).get('cat', '') or c['code']
            if cat not in cats:
                cats.add(cat)
                target.append(c)
        target = target[:args.top_n]
        target_codes = {t['code'] for t in target}

        # HWM update
        for code in portfolio:
            p = close_at(code, exec_week)
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p

        # Sells
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = close_at(code, exec_week)
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
            p = close_at(code, exec_week) or pos['buy_price']
            cash += pos['weight'] * p
            n_sells += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price'])
                          for c, pos in portfolio.items())

        # Buys
        slots = args.top_n - len(portfolio)
        if slots > 0 and equity > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            total_slot_val = (equity / args.top_n) * sf
            for bc in buy_list[:slots]:
                ep = close_at(bc['code'], exec_week)
                if ep is None or ep <= 0: continue
                weight = total_slot_val / ep
                cost = weight * ep
                if cost > cash * 0.98:
                    weight = cash * 0.98 / ep
                    cost = weight * ep
                if weight <= 0: break
                cash -= cost
                portfolio[bc['code']] = {'weight': weight, 'buy_price': ep, 'hwm': ep}
                n_buys += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price'])
                          for c, pos in portfolio.items())
        eq_curve.append({'w': exec_week, 'eq': equity, 'h': list(portfolio.keys()),
                        'nq': n_qualified, 'sf': sf})

    # Stats
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
    if n < 2: print("Not enough data"); return
    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    years = n / 52
    ann_ret = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0
    peak = eqs[0]; max_dd = 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq / peak - 1
        if dd < max_dd: max_dd = dd
    w_rets = [eqs[i]/eqs[i-1]-1 for i in range(1,n) if eqs[i-1]>0]
    if w_rets:
        avg_w = statistics.mean(w_rets)
        std_w = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52**0.5) if std_w > 0 else 0
        calmar = ann_ret / abs(max_dd * 100) if max_dd else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = calmar = win_rate = 0

    avg_nq = statistics.mean(total_qual) if total_qual else 0
    avg_na = statistics.mean(list(available_counts.values())) if available_counts else 0

    print(f"\n{'='*60}")
    print(f"  RESULTS: {label}{sizer_note}")
    print(f"{'='*60}")
    print(f"  Period:     {all_weeks[0]} ~ {all_weeks[-1]} ({n}w, {years:.1f}y)")
    print(f"  Total Ret:  {total_ret:+.1f}%")
    print(f"  Annual:     {ann_ret:+.1f}%")
    print(f"  Max DD:     {max_dd*100:.1f}%")
    print(f"  Sharpe:     {sharpe:.2f}")
    print(f"  Calmar:     {calmar:.2f}")
    print(f"  Win Rate:   {win_rate:.1f}%")
    print(f"  Trades:     {n_buys}B / {n_sells}S")
    print(f"  Avg Qual:   {avg_nq:.1f}/{avg_na:.0f} ({avg_nq/max(1,avg_na)*100:.1f}%)")
    if args.lb_mode != 'fixed':
        total_lb = sum(lb_usage.values())
        print(f"  LB usage:   {dict(sorted(lb_usage.items()))} (total {total_lb})")

    # Yearly table
    print(f"\n  {'Year':<6} {'Ret':>7} {'DD':>7} {'Hold%':>7}")
    print(f"  {'-'*30}")
    yg = defaultdict(list)
    for e in eq_curve:
        yg[e['w'][:4]].append(e)
    for yr in sorted(yg):
        es = [e['eq'] for e in yg[yr]]
        if es[0] <= 0: continue
        ret = (es[-1] / es[0] - 1) * 100
        pk = es[0]; yr_dd = 0
        for eqd in es:
            if eqd > pk: pk = eqd
            dd = (eqd / pk - 1) * 100
            if dd < yr_dd: yr_dd = dd
        hold_pct = statistics.mean(e.get('nh', len(portfolio)) for e in yg[yr]) / args.top_n * 100
        print(f"  {yr:<6} {ret:>+6.1f}% {yr_dd:>6.1f}% {hold_pct:>6.0f}%")

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    lb_suffix = f"dyn{args.lb_choppy}-{args.lb_trend}" if args.lb_mode == 'hs300' else f'lb{args.lb}'
    fname = f'bt_v6_{lb_suffix}_{ts}.json'
    fp = os.path.join(OUTPUT_DIR, fname)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump({
            'label': label+sizer_note, 'ts': datetime.now().isoformat(),
            'params': vars(args),
            'stats': {'total_ret': total_ret, 'ann_ret': ann_ret, 'max_dd': max_dd,
                      'sharpe': sharpe, 'calmar': calmar, 'win_rate': win_rate,
                      'n': n, 'years': years, 'n_buys': n_buys, 'n_sells': n_sells},
            'equity': [{'w': e['w'], 'eq': round(e['eq'], 6), 'h': e.get('h',[])} for e in eq_curve],
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {fp}")

if __name__ == '__main__':
    main()
