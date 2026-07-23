#!/usr/bin/env python3
"""
v4.3 Holiday-Aware Backtest (Clean Version)
假期周检测：每周交易量 < 20% 滚动4周均量 → 假期周，跳过
数据源: D:\QClaw_Trading\data\history_long\ (203只ETF周线)
"""
import json, os, sys, glob, statistics
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

HIST_DIR = r'D:\QClaw_Trading\data\history_long'
OUT_DIR  = r'D:\QClaw_Trading\backtest_results'
HOLIDAY_RATIO = 0.20


def load_etf(code):
    """Load weekly data for one ETF. Returns (full_weeks, normal_weeks, holidays).
    full_weeks  = [(wk, date, close, vol)]
    normal_weeks = [(wk, date, close)]  # excluding holiday weeks
    holidays = set of week keys
    Returns None on failure.
    """
    pattern1 = os.path.join(HIST_DIR, code + '.json')
    pattern2 = os.path.join(HIST_DIR, 'sh' + code + '.json')
    pattern3 = os.path.join(HIST_DIR, 'sz' + code + '.json')
    pattern4 = os.path.join(HIST_DIR, '*' + code + '.json')  # fallback
    
    for pat in [pattern1, pattern2, pattern3]:
        if os.path.exists(pat):
            fpath = pat
            break
    else:
        matches = glob.glob(pattern4)
        fpath = matches[0] if matches else None
    
    if not fpath or not os.path.exists(fpath):
        return None

    with open(fpath, 'r', encoding='utf-8') as f:
        raw = f.read().replace('NaN', 'null')
    
    try:
        records = json.loads(raw)
    except json.JSONDecodeError:
        return None
    
    if not isinstance(records, list) or len(records) < 10:
        return None
    
    # Parse weekly records
    weeks_data = {}  # wk -> (date, close, vol)
    for r in records:
        if not isinstance(r, dict):
            continue
        date_str = r.get('date', '')
        close = float(r.get('close', 0))
        vol = float(r.get('vol', 0))
        if not date_str or close <= 0:
            continue
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            year, wn, _ = dt.isocalendar()
            wk = '%d-W%02d' % (year, wn)
            if wk in weeks_data:
                old_date, old_close, old_vol = weeks_data[wk]
                # Keep latest date's close; accumulate volume
                weeks_data[wk] = (old_date, close, old_vol + vol)
            else:
                weeks_data[wk] = (date_str, close, vol)
        except (ValueError, TypeError):
            continue
    
    if len(weeks_data) < 10:
        return None
    
    # Sort by week
    sorted_wks = sorted(weeks_data.items())
    full = [(wk, date, close, vol) for wk, (date, close, vol) in sorted_wks]
    
    # Detect holidays: vol < 20% of rolling 4-week avg
    vols = [max(v[3], 1) for v in full]  # avoid zero
    holidays = set()
    for i, (wk, date, close, vol) in enumerate(full):
        avg4 = statistics.mean(vols[max(0, i-3):i+1])
        if avg4 > 1000 and vol < HOLIDAY_RATIO * avg4:
            holidays.add(wk)
    
    normal = [(wk, date, close) for wk, date, close, _ in full if wk not in holidays]
    
    return (full, normal, holidays)


def run_backtest(args):
    label = 'MA%d/%d LB%d D%d H%d [Holiday-Aware]' % (
        args.ma_s, args.ma_l, args.lb, int(args.max_dev), args.top_n)
    
    print('=' * 60)
    print('  v4.3 Holiday-Aware Backtest')
    print('  ' + label)
    print('  Range: %s ~ %s' % (args.start, args.end))
    print('=' * 60)
    
    # Get ETF codes from history directory
    all_files = [f for f in os.listdir(HIST_DIR) if f.endswith('.json')]
    etf_codes = sorted(set(
        f.replace('.json','') for f in all_files
        if f[:6].isdigit()
    ))
    print('\nLoading %d ETFs...' % len(etf_codes))
    
    # Load all ETF data
    all_full     = {}
    all_normal   = {}
    all_holidays = {}
    code_info    = {}
    loaded = 0
    
    for code in etf_codes:
        data = load_etf(code)
        if data is None:
            continue
        _, normal, holidays = data
        if len(normal) >= 30:
            all_full[code]     = data[0]
            all_normal[code]   = normal
            all_holidays[code] = holidays
            code_info[code]    = {'cat': code[:2]}  # use first 2 digits as category
            loaded += 1
    
    print('  Loaded: %d/%d' % (loaded, len(etf_codes)))
    
    if loaded < 5:
        print('ERROR: Not enough ETFs loaded'); return
    
    # Collect normal weeks across all ETFs
    norm_wk_set = set()
    for nw in all_normal.values():
        for wk, _, _ in nw:
            norm_wk_set.add(wk)
    norm_wks = sorted(wk for wk in norm_wk_set if args.start <= wk <= args.end)
    print('  Normal weeks in range: %d (%s ~ %s)' % (
        len(norm_wks), norm_wks[0], norm_wks[-1]))
    
    # Holiday stats
    total_hol = sum(len(h) for h in all_holidays.values())
    avg_hol = total_hol / len(all_holidays) if all_holidays else 0
    print('  Avg holiday weeks/ETF: %.1f' % avg_hol)
    
    # Show most common holiday weeks
    hol_cnt = defaultdict(int)
    for hs in all_holidays.values():
        for h in hs:
            if args.start <= h <= args.end:
                hol_cnt[h] += 1
    if hol_cnt:
        top_hols = sorted(hol_cnt.items(), key=lambda x: x[1], reverse=True)[:8]
        print('  Most common holiday weeks (ETF count):')
        for h, cnt in top_hols:
            print('    %s: %d ETFs' % (h, cnt))
    
    # ---- Helper functions ----
    def get_normal_closes(code, up_to_week):
        """Get closes for code for weeks < up_to_week (normal weeks only)."""
        result = []
        for wk, date, cl in all_normal.get(code, []):
            if wk >= up_to_week:
                break
            result.append(cl)
        return result
    
    def close_at(code, week):
        for wk, date, cl in all_normal.get(code, []):
            if wk == week:
                return cl
        return None
    
    def passes_filter(code, sig_week):
        """Check if code passes all filters at sig_week (normal week)."""
        cs = get_normal_closes(code, sig_week)
        n = len(cs)
        if n < args.ma_l + 1:
            return False
        
        price = cs[-1]
        ma_s = sum(cs[-args.ma_s:]) / args.ma_s
        ma_l = sum(cs[-args.ma_l:]) / args.ma_l
        
        if n > args.lb:
            mom = cs[-1] / cs[-1 - args.lb] - 1
        else:
            return False
        
        dev = price / ma_l - 1
        
        if mom <= 0: return False
        if not (price > ma_s > ma_l): return False
        if dev > args.max_dev / 100.0: return False
        
        # G3 filter
        g3_ok = True
        if n >= 2:
            if cs[-1] / cs[-2] - 1 < -0.01: g3_ok = False
        if n >= 4:
            if cs[-1] / cs[-4] - 1 < 0: g3_ok = False
        if not g3_ok: return False
        
        return True
    
    # ---- Backtest loop ----
    portfolio = {}
    cash = args.capital
    eq_curve = []
    trades = []
    n_buys = n_sells = 0
    
    for i in range(len(norm_wks) - 1):
        sig_wk  = norm_wks[i]
        exec_wk = norm_wks[i + 1]
        
        # Signals
        candidates = []
        for code in all_normal:
            if passes_filter(code, sig_wk):
                cs = get_normal_closes(code, sig_wk)
                if len(cs) > args.lb:
                    mom = cs[-1] / cs[-1 - args.lb] - 1
                    price = cs[-1]
                    ma_l = sum(cs[-args.ma_l:]) / args.ma_l
                    dev = price / ma_l - 1
                    candidates.append({'code': code, 'mom': mom, 'dev': dev})
        
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
        
        # Update HWM
        for code in list(portfolio.keys()):
            p = close_at(code, exec_wk)
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p
        
        # Sells
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = close_at(code, exec_wk)
            if p is None:
                to_sell.append((code, 'no_data')); continue
            cost_pnl = p / pos['buy_price'] - 1
            hwm_pnl  = p / pos['hwm'] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, 'stop'))
            elif code not in target_codes:
                to_sell.append((code, 'rebalance'))
        
        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = close_at(code, exec_wk) or pos['buy_price']
            cash += pos['weight'] * p
            pnl = (p / pos['buy_price'] - 1) * 100
            trades.append({'w': exec_wk, 'act': 'S', 'code': code, 'pnl': round(pnl, 2), 'reason': reason})
            n_sells += 1
        
        # Equity after sells
        equity = cash + sum(
            pos['weight'] * (close_at(c, exec_wk) or pos['buy_price'])
            for c, pos in portfolio.items()
        )
        
        # Buys
        slots = args.top_n - len(portfolio)
        if slots > 0 and equity > 0:
            slot_val = equity / args.top_n
            for bc in [t for t in target if t['code'] not in portfolio][:slots]:
                ep = close_at(bc['code'], exec_wk)
                if ep is None or ep <= 0: continue
                w = slot_val / ep
                cost = w * ep
                if cost > cash * 0.98:
                    w = cash * 0.98 / ep
                    cost = w * ep
                if w <= 0: break
                cash -= cost
                portfolio[bc['code']] = {'weight': w, 'buy_price': ep, 'hwm': ep}
                trades.append({'w': exec_wk, 'act': 'B', 'code': bc['code'], 'price': round(ep, 4)})
                n_buys += 1
        
        # Record equity
        equity = cash + sum(
            pos['weight'] * (close_at(c, exec_wk) or pos['buy_price'])
            for c, pos in portfolio.items()
        )
        eq_curve.append({'w': exec_wk, 'eq': equity, 'nh': len(portfolio),
                        'holds': list(portfolio.keys())})
    
    # ---- Statistics ----
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
    if n < 2:
        print('Not enough data'); return
    
    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    years = n / 52
    ann_ret = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    peak, max_dd = eqs[0], 0.0
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
    
    print('\n' + '=' * 60)
    print('  RESULTS')
    print('=' * 60)
    print('  Period:     %s ~ %s (%d weeks, %.1f years)' % (
        norm_wks[0], norm_wks[-1], n, years))
    print('  Total Ret:  %+.1f%%' % total_ret)
    print('  Annual:     %+.1f%%' % ann_ret)
    print('  Max DD:     %.1f%%' % (max_dd * 100))
    print('  Sharpe:     %.2f' % sharpe)
    print('  Calmar:     %.2f' % calmar)
    print('  Win Rate:   %.1f%%' % win_rate)
    print('  Trades:     %d B / %d S' % (n_buys, n_sells))
    
    # Yearly breakdown
    print('\n  %-6s %8s %8s %8s' % ('Year', 'Ret', 'DD', 'Hold%'))
    print('  ' + '-' * 32)
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
        print('  %-6s %+7.1f%% %7.1f%% %7.0f%%' % (yr, ret, dd*100, hold_pct))
    
    # Comparison with baseline (no holiday skip)
    print('\n  [Holiday weeks skipped in backtest: %d weeks -> %d normal weeks]' % (
        len(norm_wks) + 1 - n, n))
    
    # Save result
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(OUT_DIR, 'bt_holiday_%s.json' % ts)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            'label': label, 'args': vars(args),
            'total_ret': round(total_ret, 2),
            'ann_ret': round(ann_ret, 2),
            'max_dd': round(max_dd * 100, 2),
            'sharpe': round(sharpe, 3),
            'calmar': round(calmar, 2),
            'win_rate': round(win_rate, 1),
            'n_buys': n_buys, 'n_sells': n_sells,
            'n_weeks': n, 'years': round(years, 1),
            'n_etfs': loaded,
            'avg_holiday_per_etf': round(avg_hol, 1),
        }, f, ensure_ascii=False, indent=2)
    print('\n  Saved: %s' % out_file)


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
    ap.add_argument('--end', type=str, default='2026-W24')
    run_backtest(ap.parse_args())
