"""
ATR Factor Test for v4.5 Strategy - Precomputed version
Tests: ATR filter (skip when volatility contracting), ATR boost (score multiplier)
"""
import json, os, sys, glob, statistics, argparse
from datetime import datetime
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'
POOL_FILE = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def load_history_full(code):
    """Load full OHLCV data for ATR computation"""
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
                    return None
                weeks = {}
                for r in recs:
                    ds = r.get('date', '')
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        y, w, _ = dt.isocalendar()
                        wk = f'{y}-W{w:02d}'
                        if wk not in weeks or ds > weeks[wk][0]:
                            weeks[wk] = (ds, r.get('close',0), r.get('high',0), r.get('low',0), r.get('open',0))
                    except:
                        pass
                sorted_wks = sorted(weeks.items())
                return [{'w': wk, 'close': cl, 'high': hi, 'low': lo, 'open': op}
                        for wk, (ds, cl, hi, lo, op) in sorted_wks]
            except:
                pass
    return None

def precompute_atr_ratios(data, fast=14, slow=21):
    """Precompute ATR ratio for every week of an ETF. Returns dict week->ratio"""
    n = len(data)
    if n < slow + 1:
        return {}
    # Compute TR for each week
    trs = [None] * n
    for i in range(1, n):
        h = data[i]['high']
        l = data[i]['low']
        pc = data[i-1]['close']
        trs[i] = max(h - l, abs(h - pc), abs(l - pc))
    
    # Compute rolling SMA-based ATR and ratio for each week
    result = {}
    for i in range(slow, n):
        vals = [trs[j] for j in range(i-slow+1, i+1) if trs[j] is not None]
        if len(vals) < slow:
            continue
        fast_vals = vals[-fast:]
        fast_atr = sum(fast_vals) / fast
        slow_atr = sum(vals) / slow
        result[data[i]['w']] = fast_atr / slow_atr if slow_atr > 0 else None
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atr-filter', type=float, default=None,
                    help='Skip ETFs with ATR ratio below threshold (e.g. 0.85)')
    ap.add_argument('--atr-boost', type=float, default=None,
                    help='Score *= (1 + boost * (atr_ratio - 1))')
    ap.add_argument('--max-dev', type=float, default=15)
    ap.add_argument('--top-n', type=int, default=3)
    ap.add_argument('--start', type=str, default='2010-W01')
    ap.add_argument('--end', type=str, default='2026-W30')
    args = ap.parse_args()

    w1, w3 = 0.4, 0.4
    label = f"SC40-40-20 D{args.max_dev:.0f} H{args.top_n}"
    if args.atr_filter:
        label += f" ATRf{args.atr_filter:.2f}"
    if args.atr_boost:
        label += f" ATRb{args.atr_boost:.2f}"

    print(f"\n{'='*60}")
    print(f"  ATR Factor Test: {label}")
    print(f"{'='*60}")

    etfs = load_pool()
    print(f"\nLoading data and precomputing ATR ratios...")
    
    all_data = {}      # code -> full OHLC data
    all_close = {}     # code -> [(week, close)]
    all_atr = {}       # code -> {week: atr_ratio}
    code_info = {}
    
    for etf in etfs:
        code = etf['code']
        s = load_history_full(code)
        if s and len(s) >= 30:
            all_data[code] = s
            all_close[code] = [(r['w'], r['close']) for r in s]
            all_atr[code] = precompute_atr_ratios(s, 14, 21)
            code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}

    print(f"  Loaded: {len(all_data)}/{len(etfs)}, missing: {len(etfs)-len(all_data)}")

    weeks_set = set()
    for s in all_close.values():
        for w, c in s:
            weeks_set.add(w)
    all_weeks = sorted(w for w in weeks_set if args.start <= w <= args.end)
    print(f"  Weeks: {len(all_weeks)} ({all_weeks[0]} ~ {all_weeks[-1]})")

    def closes_until(code, week):
        return [c for w, c in all_close.get(code, []) if w <= week]

    def close_at(code, week):
        for w, c in all_close.get(code, []):
            if w == week: return c
        return None

    def get_signal(code, week):
        cs = closes_until(code, week)
        n = len(cs)
        if n < 22: return None
        price = cs[-1]
        ma_s = sum(cs[-5:]) / 5
        ma_l = sum(cs[-21:]) / 21
        mom3w = cs[-1] / cs[-4] - 1
        mom1w = cs[-1] / cs[-2] - 1 if n >= 2 else mom3w
        mom8w = cs[-1] / cs[-8] - 1 if n >= 9 else mom3w
        dev = price / ma_l - 1

        # Standard filters
        if mom3w <= 0: return None
        if not (price > ma_s > ma_l): return None
        if dev > args.max_dev / 100: return None
        if mom1w < -0.01: return None

        # ATR filter
        atr_ratio = all_atr.get(code, {}).get(week)
        if args.atr_filter is not None:
            if atr_ratio is None or atr_ratio < args.atr_filter:
                return None

        score = w1 * mom1w + w3 * mom3w + (1-w1-w3) * mom8w

        # ATR boost
        if args.atr_boost is not None and args.atr_boost > 0 and atr_ratio is not None and atr_ratio > 0:
            score = score * (1 + args.atr_boost * (atr_ratio - 1))

        return {'code': code, 'close': price, 'score': score}

    # Precompute available counts
    first_avail = {}
    for code, s in all_close.items():
        first_avail[code] = s[21][0] if len(s) >= 22 else None
    avail_counts = {}
    for w in all_weeks:
        cnt = sum(1 for c in first_avail if first_avail[c] is not None and first_avail[c] <= w)
        avail_counts[w] = cnt

    portfolio = {}
    cash = 1.0
    eq_curve = []
    n_buys = n_sells = 0

    print(f"\n  Running backtest...")
    for i in range(len(all_weeks) - 1):
        sig_week = all_weeks[i]
        exec_week = all_weeks[i + 1]

        candidates = []
        for code in all_close:
            sig = get_signal(code, sig_week)
            if sig:
                candidates.append(sig)

        n_qualified = len(candidates)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        target = candidates[:args.top_n]
        target_codes = {t['code'] for t in target}

        for code in portfolio:
            p = close_at(code, sig_week)
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p

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

        slots = args.top_n - len(portfolio)
        if slots > 0 and equity > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            slot_val = equity / args.top_n
            for bc in buy_list[:slots]:
                ep = close_at(bc['code'], sig_week)
                if ep is None or ep <= 0: continue
                weight = slot_val / ep
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
        eq_curve.append({'w': exec_week, 'eq': equity, 'nh': len(portfolio),
                        'nq': n_qualified, 'h': list(portfolio.keys())})

    # Stats
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
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
        sharpe = calmar = win_rate = 0.0

    yg = defaultdict(list)
    for e in eq_curve:
        yg[e['w'][:4]].append(e)
    
    print(f"\n{'='*60}")
    print(f"  RESULTS: {label}")
    print(f"{'='*60}")
    print(f"  Period:     {all_weeks[0]} ~ {all_weeks[-1]} ({n}w, {years:.1f}y)")
    print(f"  Total Ret:  {total_ret:+.1f}%")
    print(f"  Annual:     {ann_ret:+.1f}%")
    print(f"  Max DD:     {max_dd*100:.1f}%")
    print(f"  Sharpe:     {sharpe:.2f}")
    print(f"  Calmar:     {calmar:.2f}")
    print(f"  Win Rate:   {win_rate:.1f}%")
    print(f"  Trades:     {n_buys}B / {n_sells}S")

    print(f"\n  {'Year':<6} {'Ret':>7}")
    print(f"  {'-'*20}")
    for yr in sorted(yg):
        es = [e['eq'] for e in yg[yr]]
        if es[0] <= 0: continue
        ret = (es[-1] / es[0] - 1) * 100
        print(f"  {yr:<6} {ret:>+6.1f}%")

if __name__ == '__main__':
    main()
