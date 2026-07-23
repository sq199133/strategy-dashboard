#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.6 回测 - 可配置G3过滤的1周动量阈值
用法: python backtest_v4_6.py --mom1w-threshold 0.0
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
                recs = d if isinstance(d, list) else d.get('records', [])
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
                        if week_key not in weeks or ds > weeks[week_key][0]:
                            weeks[week_key] = (ds, cl)
                    except:
                        pass
                sw = sorted(weeks.items())
                return [(w, cl) for w, (ds, cl) in sw]
            except:
                continue
    return None


def load_hs300_momentum():
    hs300 = load_history('000300')
    if not hs300 or len(hs300) < 5:
        return None
    weeks = [w for w, c in hs300]
    closes = [c for w, c in hs300]
    mom_map = {}
    for i in range(5, len(closes)):
        mom = closes[i] / closes[i-3] - 1
        mom_map[weeks[i]] = mom
    return mom_map


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
    ap.add_argument('--end', type=str, default='2026-W18')
    ap.add_argument('--hs300-threshold', type=float, default=-100.0)
    ap.add_argument('--mom1w-threshold', type=float, default=-1.0, help='G3过滤1周动量阈值(默认-1.0%%)')
    ap.add_argument('--output', type=str, default=None)
    args = ap.parse_args()

    label = f"MA{args.ma_s}/{args.ma_l} LB{args.lb} D{args.max_dev} H{args.top_n} MOM1W{args.mom1w_threshold:+.1f}"
    print(f"{'='*60}")
    print(f"  v4.6 Backtest: {label}")
    print(f"  G3 MOM1W threshold: {args.mom1w_threshold:+.1f}%")
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

    hs300_mom = load_hs300_momentum()
    if hs300_mom:
        print(f"  HS300 momentum loaded: {len(hs300_mom)} weeks\n")
    else:
        print(f"  Warning: HS300 data not available, market filter disabled\n")

    def closes_until(code, week):
        return [c for w, c in all_series.get(code, []) if w <= week]

    def close_at(code, week):
        for w, c in all_series.get(code, []):
            if w == week: return c
            if w > week: return None
        return None

    # Signal function with configurable G3 MOM1W threshold
    def get_signal(code, week):
        cs = closes_until(code, week)
        n = len(cs)
        if n < args.ma_l + 1:
            return None

        if hs300_mom and week in hs300_mom:
            if hs300_mom[week] <= args.hs300_threshold / 100:
                return None

        price = cs[-1]
        ma_s = sum(cs[-args.ma_s:]) / args.ma_s
        ma_l = sum(cs[-args.ma_l:]) / args.ma_l
        mom = cs[-1] / cs[-args.lb] - 1 if n > args.lb else None
        dev = price / ma_l - 1

        if mom is None or mom <= 0:
            return None
        if not (price > ma_s > ma_l):
            return None
        if dev > args.max_dev / 100.0:
            return None

        # G3 filter with configurable MOM1W threshold
        g3_pass = True
        if len(cs) >= 2:
            mom1w = cs[-1] / cs[-2] - 1
            if mom1w < args.mom1w_threshold / 100.0:  # <-- 可配置阈值
                g3_pass = False
        if len(cs) >= 4:
            mom3w = cs[-1] / cs[-4] - 1
            if mom3w < 0:
                g3_pass = False

        if not g3_pass:
            return None

        return {'code': code, 'close': price, 'mom': mom, 'dev': dev}

    # Backtest loop (same as v4.3)
    portfolio = {}
    cash = args.capital
    eq_curve = []
    trades = []
    n_buys = n_sells = 0

    for i in range(len(all_weeks) - 1):
        sig_week = all_weeks[i]
        exec_week = all_weeks[i + 1]

        candidates = []
        for code in all_series:
            sig = get_signal(code, sig_week)
            if sig:
                candidates.append(sig)

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

        for code in portfolio:
            p = close_at(code, exec_week)
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p

        to_sell = []
        for code, pos in list(portfolio.items()):
            p = close_at(code, exec_week)
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
            p = close_at(code, exec_week) or pos['buy_price']
            cash += pos['weight'] * p
            pnl = (p / pos['buy_price'] - 1) * 100
            trades.append({'w': exec_week, 'act': 'S', 'code': code, 'pnl': round(pnl, 2), 'reason': reason})
            n_sells += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price'])
                          for c, pos in portfolio.items())

        slots = args.top_n - len(portfolio)
        if slots > 0 and equity > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            slot_val = equity / args.top_n
            for bc in buy_list[:slots]:
                exec_price = close_at(bc['code'], exec_week)
                if exec_price is None or exec_price <= 0:
                    continue
                weight = slot_val / exec_price
                cost = weight * exec_price
                if cost > cash * 0.98:
                    weight = cash * 0.98 / exec_price
                    cost = weight * exec_price
                if weight <= 0:
                    break
                cash -= cost
                portfolio[bc['code']] = {'weight': weight, 'buy_price': exec_price, 'hwm': exec_price}
                trades.append({'w': exec_week, 'act': 'B', 'code': bc['code'], 'price': round(exec_price, 4)})
                n_buys += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price'])
                          for c, pos in portfolio.items())
        eq_curve.append({'w': exec_week, 'eq': equity, 'nh': len(portfolio),
                        'cash': round(cash, 4), 'holds': list(portfolio.keys())})

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
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52**0.5)
        calmar = ann_ret / abs(max_dd * 100) if max_dd else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = calmar = win_rate = 0

    print(f"{'='*60}")
    print(f"  RESULTS: {label}")
    print(f"{'='*60}\n")
    print(f"  Period:     {all_weeks[0]} ~ {all_weeks[-1]} ({n}w, {years:.1f}y)")
    print(f"  Total Ret:  {total_ret:+.1f}%")
    print(f"  Annual:     {ann_ret:+.1f}%")
    print(f"  Max DD:     {max_dd*100:.1f}%")
    print(f"  Sharpe:     {sharpe:.2f}")
    print(f"  Calmar:     {calmar:.2f}")
    print(f"  Win Rate:   {win_rate:.1f}%")
    print(f"  Trades:     {n_buys}B / {n_sells}S")

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
        yearly_max_dd = 0
        for eq in es:
            if eq > pk: pk = eq
            dd = (eq / pk - 1) * 100
            if dd < yearly_max_dd: yearly_max_dd = dd
        hold_pct = statistics.mean(e['nh'] for e in yg[yr]) / args.top_n * 100
        print(f"  {yr:<6} {ret:>+6.1f}% {yearly_max_dd:>6.1f}% {hold_pct:>6.0f}%")

    # Save JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if args.output:
        fp = args.output if os.path.isabs(args.output) else os.path.join(OUTPUT_DIR, args.output)
    else:
        fname = f'bt_v4_6_mom1w_{args.mom1w_threshold:+.0f}_{ts}.json'
        fp = os.path.join(OUTPUT_DIR, fname)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump({
            'label': label, 'ts': datetime.now().isoformat(),
            'params': vars(args),
            'stats': {'total_ret': total_ret, 'ann_ret': ann_ret, 'max_dd': max_dd,
                      'sharpe': sharpe, 'calmar': calmar, 'win_rate': win_rate,
                      'n': n, 'years': years, 'n_buys': n_buys, 'n_sells': n_sells},
            'equity': [{'w': e['w'], 'eq': round(e['eq'], 6), 'nh': e['nh']} for e in eq_curve],
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {fp}")


if __name__ == '__main__':
    main()
