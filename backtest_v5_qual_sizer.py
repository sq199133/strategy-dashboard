#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.0 Qual-Sizer Backtest: Position sizing based on qualified ETF count
When fewer ETFs pass the scan, reduce position size (market momentum is weak).
When many qualify, go full allocation.

Usage: python backtest_v5_qual_sizer.py [--qual-sizer step:5:0.5] [其他参数同v4]
"""
import json, os, sys, glob, statistics
from datetime import datetime as dt_mod
from collections import defaultdict

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'


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
                        dt = dt_mod.strptime(ds, '%Y-%m-%d')
                        y, w, _ = dt.isocalendar()
                        week_key = f'{y}-W{w:02d}'
                        if week_key not in weeks or ds > weeks[week_key][0]:
                            weeks[week_key] = (ds, cl)
                    except:
                        pass
                sw = sorted(weeks.items())
                return [(w, cl) for w, (ds, cl) in sw]
            except:
                continue
    return None


def compute_size_factor(n_qualified, n_available, config):
    """
    config: "none" -> 1.0
    
    Absolute thresholds:
    config: "step:N:F" -> qualified count < N: F, else 1.0
    config: "step2:N1:F1,N2:F2" -> count < N1: F1, count < N2: F2, else 1.0
    config: "linear:N" -> min(1.0, count/N)
    
    Percentage-based (market-aware):
    config: "steppct:P:F" -> qualified/total < P fraction: F, else 1.0
             e.g. steppct:0.05:0.50 -> <5% of available ETFs qualify: half pos
    config: "linearpct:P" -> min(1.0, (qualified/total) / P)
    """
    if config == 'none' or config is None:
        return 1.0
    
    parts = config.split(':')
    mode = parts[0]
    
    if mode == 'step':
        thresh = int(parts[1])
        frac = float(parts[2])
        return frac if n_qualified < thresh else 1.0
    
    elif mode == 'step2':
        pairs = config[len('step2:'):].split(',')
        for pair in pairs:
            t, f = pair.split(':')
            if n_qualified < int(t):
                return float(f)
        return 1.0
    
    elif mode == 'linear':
        cap = int(parts[1])
        return min(1.0, n_qualified / cap)
    
    elif mode == 'steppct':
        # steppct:P:F e.g. steppct:0.05:0.50 -> <5% → half
        pct_thresh = float(parts[1])
        frac = float(parts[2])
        ratio = n_qualified / max(1, n_available)
        return frac if ratio < pct_thresh else 1.0
    
    elif mode == 'linearpct':
        # linearpct:P e.g. linearpct:0.05 -> ratio / 0.05, capped at 1.0
        pct_cap = float(parts[1])
        ratio = n_qualified / max(1, n_available)
        return min(1.0, ratio / pct_cap)
    
    else:
        return 1.0


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
    ap.add_argument('--end', type=str, default='2026-W30')
    ap.add_argument('--hs300-threshold', type=float, default=-100.0)
    ap.add_argument('--mom1w-threshold', type=float, default=-100.0, help='G3 1-week momentum threshold (%)')
    ap.add_argument('--mom3w-threshold', type=float, default=-100.0, help='G3 3-week momentum threshold (%)')
    ap.add_argument('--score-mode', type=str, default='lb3', choices=['lb3','composite'], help='Score mode: lb3 (default) or composite (multi-period)')
    ap.add_argument('--score-w1', type=float, default=0.4, help='mom1w weight for composite')
    ap.add_argument('--score-w3', type=float, default=0.4, help='mom3w weight for composite (mom8w=1-w1-w3)')
    ap.add_argument('--no-ma-filter', action='store_true', help='Skip MA5 > MA21 trend filter')
    ap.add_argument('--output', type=str, default=None)
    ap.add_argument('--qual-sizer', type=str, default='none',
                    help='Qual count sizer: step:N:F | steppct:P:F | linear:N | line arpct:P | step2:N1:F1,N2:F2')
    ap.add_argument('--atr-filter', type=float, default=None,
                    help='ATR contraction filter: skip when ATR ratio < threshold (0.80-0.95)')
    args = ap.parse_args()

    m1, m3 = args.mom1w_threshold, args.mom3w_threshold
    g3_label = f" G3M1W{m1:+.0f}M3W{m3:+.0f}" if abs(m1 + 1) > 0.01 or abs(m3) > 0.01 else ''
    w1, w3 = args.score_w1, args.score_w3
    sc_label = f" SC{int(w1*100):d}{int(w3*100):d}{int(100-w1*100-w3*100):d}" if args.score_mode == 'composite' else ''
    label = f"MA{args.ma_s}/{args.ma_l} LB{args.lb} D{args.max_dev} H{args.top_n}{g3_label}{sc_label}"
    sizer_note = f"+QS:{args.qual_sizer}" if args.qual_sizer != 'none' else ''
    print(f"{'='*60}")
    print(f"  v5.0 Qual-Sizer Backtest: {label}{sizer_note}")
    print(f"  Range: {args.start} ~ {args.end}")
    print(f"{'='*60}\n")

    etfs = load_pool()
    print("Loading...")

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

    def get_signal(code, week):
        cs = closes_until(code, week)
        n = len(cs)
        if n < args.ma_l + 1:
            return None
        price = cs[-1]
        ma_s = sum(cs[-args.ma_s:]) / args.ma_s
        ma_l = sum(cs[-args.ma_l:]) / args.ma_l
        mom = cs[-1] / cs[-args.lb] - 1 if n > args.lb else None
        dev = price / ma_l - 1
        if mom is None or mom <= 0:
            return None
        if not args.no_ma_filter and not (price > ma_s > ma_l):
            return None
        if dev > args.max_dev / 100.0:
            return None
        # G3
        if len(cs) >= 2:
            mom1w = cs[-1] / cs[-2] - 1
            if mom1w < args.mom1w_threshold / 100.0:
                return None
        if len(cs) >= 4:
            mom3w = cs[-1] / cs[-4] - 1
            if mom3w < args.mom3w_threshold / 100.0:
                return None
        # ATR contraction filter
        if args.atr_filter is not None:
            ar = all_atr.get(code, {}).get(week, None)
            # Only filter if ATR data exists
            if ar is not None and ar < args.atr_filter:
                return None
        mom1w_val = cs[-1] / cs[-2] - 1 if len(cs) >= 2 else mom
        mom8w_val = cs[-1] / cs[-8] - 1 if len(cs) >= 9 else mom
        score = mom if args.score_mode == 'lb3' else (args.score_w1 * mom1w_val + args.score_w3 * mom + (1-args.score_w1-args.score_w3) * mom8w_val)
        return {'code': code, 'close': price, 'mom': mom, 'mom1w': mom1w_val, 'mom8w': mom8w_val, 'score': score, 'dev': dev}

    # Precompute available ETF count per week (ETFs with enough history)
    print("  Precomputing available counts per week...")
    ma_l = args.ma_l
    first_avail_week = {}  # code -> first week where n_closes >= ma_l+1
    for code, series in all_series.items():
        if len(series) >= ma_l + 1:
            first_avail_week[code] = series[ma_l][0]
        else:
            first_avail_week[code] = None
    
    available_counts = {}
    for w in all_weeks:
        cnt = sum(1 for c in first_avail_week if first_avail_week[c] is not None and first_avail_week[c] <= w)
        available_counts[w] = cnt
    
    print(f"    Available ETFs range: min={min(available_counts.values())} ~ max={max(available_counts.values())}")

    # ATR precomputation
    all_full = {}
    all_atr = {}
    if args.atr_filter is not None:
        from datetime import datetime as dt_atr
        print(f"  Loading OHLC data for ATR (filter={args.atr_filter:.2f})...")
        for etf in etfs:
            code = etf['code']
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
                        if not recs or not isinstance(recs[0], dict) or 'high' not in recs[0]:
                            break
                        weeks = {}
                        for r in recs:
                            ds = r.get('date', '')
                            try:
                                dt = dt_atr.strptime(ds, '%Y-%m-%d')
                                y, w, _ = dt.isocalendar()
                                wk = f'{y}-W{w:02d}'
                                if wk not in weeks or ds > weeks[wk][0]:
                                    weeks[wk] = (ds, r.get('close',0), r.get('high',0), r.get('low',0))
                            except:
                                pass
                        sorted_wks = sorted(weeks.items())
                        data = [{'w': wk, 'close': cl, 'high': hi, 'low': lo} for wk, (ds, cl, hi, lo) in sorted_wks]
                        if len(data) >= 30:
                            all_full[code] = data
                            # Precompute ATR ratios
                            trs = [None] * len(data)
                            for i in range(1, len(data)):
                                h = data[i]['high']
                                l = data[i]['low']
                                pc = data[i-1]['close']
                                trs[i] = max(h - l, abs(h - pc), abs(l - pc))
                            atrs = {}
                            for i in range(21, len(data)):
                                vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
                                if len(vals) >= 21:
                                    fast = sum(vals[-14:]) / 14
                                    slow = sum(vals) / 21
                                    if slow > 0:
                                        atrs[data[i]['w']] = fast / slow
                            all_atr[code] = atrs
                    except:
                        pass
                    break
        print(f"    ATR loaded: {len(all_full)}/{len(etfs)}")

    portfolio = {}
    cash = args.capital
    eq_curve = []
    n_buys = n_sells = 0

    total_qual_counts = []
    total_avail_counts = []

    for i in range(len(all_weeks) - 1):
        sig_week = all_weeks[i]
        exec_week = all_weeks[i + 1]

        # Signal
        candidates = []
        for code in all_series:
            sig = get_signal(code, sig_week)
            if sig:
                candidates.append(sig)

        # Track qualified count (before dedup)
        n_qualified = len(candidates)
        total_qual_counts.append(n_qualified)

        # Number of available ETFs this week
        n_available = available_counts.get(sig_week, 1)
        total_avail_counts.append(n_available)

        # Size factor
        size_factor = compute_size_factor(n_qualified, n_available, args.qual_sizer)
        if size_factor < 0.01:
            size_factor = 0.0

        candidates.sort(key=lambda x: x['score'], reverse=True)
        cats = set()
        target = []
        for c in candidates:
            cat = code_info.get(c['code'], {}).get('cat', '') or c['code']
            if cat not in cats:
                cats.add(cat)
                target.append(c)
        target = target[:args.top_n]
        target_codes = {t['code'] for t in target}

        # Exec: mark holdings (using sig_week close = Monday open of exec_week)
        for code in portfolio:
            p = close_at(code, sig_week)
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p

        # Sells (at sig_week close = Monday open of exec_week)
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = close_at(code, sig_week)
            if p is None:
                to_sell.append((code, 'no_data'))
                continue
            cost_pnl = p / pos['buy_price'] - 1
            hwm_pnl = p / pos['hwm'] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, 'stop'))
            elif code not in target_codes:
                to_sell.append((code, 'rebalance'))

        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = close_at(code, sig_week) or pos['buy_price']
            cash += pos['weight'] * p
            n_sells += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price'])
                          for c, pos in portfolio.items())

        # Buys (at sig_week close = Monday open of exec_week)
        slots = args.top_n - len(portfolio)
        if slots > 0 and equity > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            
            # Key change: multiply slot allocation by size_factor
            total_slot_val = (equity / args.top_n) * size_factor
            
            for bc in buy_list[:slots]:
                exec_price = close_at(bc['code'], sig_week)
                if exec_price is None or exec_price <= 0:
                    continue
                weight = total_slot_val / exec_price
                cost = weight * exec_price
                if cost > cash * 0.98:
                    weight = cash * 0.98 / exec_price
                    cost = weight * exec_price
                if weight <= 0:
                    break
                cash -= cost
                portfolio[bc['code']] = {'weight': weight, 'buy_price': exec_price, 'hwm': exec_price}
                n_buys += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price'])
                          for c, pos in portfolio.items())
        eq_curve.append({'w': exec_week, 'eq': equity, 'nh': len(portfolio),
                        'nq': n_qualified, 'sf': size_factor,
                        'h': list(portfolio.keys())})

    # Stats
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
    if n < 2:
        print("Not enough data"); return

    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    years = n / 52
    ann_ret = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0

    peak = eqs[0]
    max_dd = 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq / peak - 1
        if dd < max_dd: max_dd = dd

    w_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
    if w_rets:
        avg_w = statistics.mean(w_rets)
        std_w = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52**0.5) if std_w > 0 else 0
        calmar = ann_ret / abs(max_dd * 100) if max_dd else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = calmar = win_rate = 0

    avg_nq = statistics.mean(total_qual_counts) if total_qual_counts else 0
    avg_na = statistics.mean(total_avail_counts) if total_avail_counts else 0

    print(f"{'='*60}")
    print(f"  RESULTS: {label}{sizer_note}")
    print(f"{'='*60}\n")
    print(f"  Period:     {all_weeks[0]} ~ {all_weeks[-1]} ({n}w, {years:.1f}y)")
    print(f"  Total Ret:  {total_ret:+.1f}%")
    print(f"  Annual:     {ann_ret:+.1f}%")
    print(f"  Max DD:     {max_dd*100:.1f}%")
    print(f"  Sharpe:     {sharpe:.2f}")
    print(f"  Calmar:     {calmar:.2f}")
    print(f"  Win Rate:   {win_rate:.1f}%")
    print(f"  Trades:     {n_buys}B / {n_sells}S")
    print(f"  Avg Qual:   {avg_nq:.1f}/{avg_na:.0f} ({avg_nq/max(1,avg_na)*100:.1f}%)")
    is_pct = 'pct' in args.qual_sizer
    if is_pct:
        ratios = [total_qual_counts[i]/max(1,total_avail_counts[i])*100 for i in range(len(total_qual_counts))]
        print(f"  Qual Ratio:  min={min(ratios):.1f}% med={statistics.median(ratios):.1f}% max={max(ratios):.1f}%")

    # Yearly
    print(f"\n  {'Year':<6} {'Ret':>7} {'DD':>7} {'Hold%':>7}")
    print(f"  {'-'*30}")
    yg = defaultdict(list)
    for e in eq_curve:
        yg[e['w'][:4]].append(e)
    for yr in sorted(yg):
        es = [e['eq'] for e in yg[yr]]
        if es[0] <= 0: continue
        ret = (es[-1] / es[0] - 1) * 100
        pk = es[0]
        yr_dd = 0
        for eq in es:
            if eq > pk: pk = eq
            dd = (eq / pk - 1) * 100
            if dd < yr_dd: yr_dd = dd
        hold_pct = statistics.mean(e['nh'] for e in yg[yr]) / args.top_n * 100
        print(f"  {yr:<6} {ret:>+6.1f}% {yr_dd:>6.1f}% {hold_pct:>6.0f}%")

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = dt_mod.now().strftime('%Y%m%d_%H%M%S')
    label_safe = sizer_note.replace(':', '-').replace(',', '_')
    fname = f'bt_v5_{args.qual_sizer.replace(":", "-").replace(",", "_")}_{ts}.json'
    fp = os.path.join(OUTPUT_DIR, fname)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump({
            'label': f'{label}{sizer_note}', 'ts': dt_mod.now().isoformat(),
            'params': vars(args),
            'stats': {'total_ret': total_ret, 'ann_ret': ann_ret, 'max_dd': max_dd,
                      'sharpe': sharpe, 'calmar': calmar, 'win_rate': win_rate,
                      'n': n, 'years': years, 'n_buys': n_buys, 'n_sells': n_sells},
            'equity': [{'w': e['w'], 'eq': round(e['eq'], 6), 'nh': e['nh'], 'nq': e.get('nq',0), 'h': e.get('h',[])} for e in eq_curve],
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {fp}")


if __name__ == '__main__':
    main()
