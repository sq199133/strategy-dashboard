#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案B v2: 腾讯日线数据（2023-10至今）+ 周末/节假日处理
- 数据源: 腾讯API qfqday/day（ETF日线仅支持2023-10起）
- 调仓: 每周五信号，下周一执行
- 对比: 周线版(v4.3) vs 日线版(B)
"""
import sys, json, os, glob, time as time_module, statistics
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime, timedelta

DAILY_DIR = r'D:\QClaw_Trading\data\daily_tx'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

MA_S, MA_L, LB, MAX_DEV, TOP_N = 5, 21, 5, 10, 2
INIT_CAPITAL = 1_000_000

def load_daily(code):
    for pat in [code, f'sh{code}', f'sz{code}']:
        matches = glob.glob(os.path.join(DAILY_DIR, f'{pat}.json'))
        if not matches:
            matches = glob.glob(os.path.join(DAILY_DIR, f'*{code}*.json'))
        if matches:
            try:
                with open(matches[0], 'r', encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d = json.loads(raw)
                recs = d.get('records', [])
                return recs
            except:
                continue
    return None

def download_live(code, prefix='sz', max_retries=2):
    """实时拉取单只ETF日线（腾讯API，只拉需要的日期段）"""
    import urllib.request
    all_records = []
    cur_start = '2023-10-01'
    for attempt in range(max_retries):
        try:
            url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_day'
                  f'&param={prefix}{code},day,{cur_start},,640,qfq')
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            d = json.loads(raw.split('=', 1)[1])
            node = d.get('data', {}).get(f'{prefix}{code}', {})
            qfq = node.get('qfqday', [])
            raw = node.get('day', [])
            days = qfq if qfq else raw
            if not days:
                if attempt < max_retries - 1:
                    time_module.sleep(2)
                    continue
                return None
            for rec in days:
                if len(rec) >= 6:
                    all_records.append({'date': rec[0], 'close': float(rec[2])})
            if len(days) < 640:
                break
            cur_start = days[-1][0]
        except Exception as e:
            if attempt < max_retries - 1:
                time_module.sleep(2)
            else:
                return None
    return all_records if len(all_records) > 50 else None

def get_fridays(start_date, end_date, all_dates_set):
    """获取交易日范围内的所有周五"""
    fridays = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() == 4:
            ds = cur.strftime('%Y-%m-%d')
            if ds in all_dates_set:
                fridays.append(cur)
        cur += timedelta(days=1)
    return fridays

def get_next_trading_day(date, all_dates_sorted, direction=1):
    """从date出发找下一个交易日（direction=1往后，-1往前）"""
    ds = date.strftime('%Y-%m-%d')
    if ds in all_dates_sorted:
        idx = all_dates_sorted.index(ds)
        next_idx = idx + direction
        if 0 <= next_idx < len(all_dates_sorted):
            return datetime.strptime(all_dates_sorted[next_idx], '%Y-%m-%d')
    return None

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--ma-s', type=int, default=MA_S)
    ap.add_argument('--ma-l', type=int, default=MA_L)
    ap.add_argument('--lb', type=int, default=LB)
    ap.add_argument('--max-dev', type=float, default=MAX_DEV)
    ap.add_argument('--top-n', type=int, default=TOP_N)
    ap.add_argument('--start', type=str, default='2023-10-01')
    ap.add_argument('--end', type=str, default='2026-06-12')
    ap.add_argument('--live-fetch', action='store_true', help='实时拉取日线数据（而非从本地加载）')
    ap.add_argument('--output', type=str, default=None)
    args = ap.parse_args()

    start_dt = datetime.strptime(args.start, '%Y-%m-%d')
    end_dt = datetime.strptime(args.end, '%Y-%m-%d')

    label = f"Daily MA{args.ma_s}/{args.ma_l} LB{args.lb} D{args.max_dev} H{args.top_n}"
    print(f"{'='*60}")
    print(f"  {label} (方案B v2: 日线版)")
    print(f"  Range: {args.start} ~ {args.end}")
    print(f"  Data mode: {'live-fetch' if args.live_fetch else 'local-files'}")
    print(f"{'='*60}\n")

    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    etfs = data.get('data', data.get('etfs', []))

    all_series = {}
    code_info = {}
    all_dates_set = set()
    all_dates_sorted = []
    missing = 0

    for etf in etfs:
        code = etf['code']
        recs = None
        
        if args.live_fetch:
            # 实时拉取
            for prefix in ['sz', 'sh']:
                recs = download_live(code, prefix)
                if recs and len(recs) > 50:
                    break
                recs = None
        else:
            recs = load_daily(code)
        
        if recs and len(recs) >= MA_L + 5:
            series = [(r['date'], r['close']) for r in recs
                      if r.get('date') and r.get('close') and r['close'] > 0]
            if len(series) >= MA_L + 5:
                all_series[code] = series
                code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}
                for ds, c in series:
                    all_dates_set.add(ds)
            else:
                missing += 1
        else:
            missing += 1

    all_dates_sorted = sorted(all_dates_set)
    print(f"  Loaded: {len(all_series)}/{len(etfs)}, missing: {missing}")
    print(f"  Trading days: {len(all_dates_sorted)} ({all_dates_sorted[0]} ~ {all_dates_sorted[-1]})")

    fridays = get_fridays(start_dt, end_dt, all_dates_set)
    print(f"  Fridays: {len(fridays)} ({fridays[0].strftime('%Y-%m-%d')} ~ {fridays[-1].strftime('%Y-%m-%d')})")

    if not fridays:
        print("No trading Fridays found in range"); return

    def closes_until(code, date_str):
        return [(ds, c) for ds, c in all_series.get(code, []) if ds <= date_str]

    def close_at(code, date_str):
        for ds, c in all_series.get(code, []):
            if ds == date_str: return c
            if ds > date_str: return None
        return None

    def get_signal(code, date_str):
        cs = closes_until(code, date_str)
        n = len(cs)
        if n < args.ma_l + 1:
            return None
        closes = [c for ds, c in cs]
        price = closes[-1]
        ma_s = sum(closes[-args.ma_s:]) / args.ma_s
        ma_l = sum(closes[-args.ma_l:]) / args.ma_l
        mom = closes[-1] / closes[-args.lb] - 1 if n > args.lb else None
        dev = price / ma_l - 1
        if mom is None or mom <= 0: return None
        if not (price > ma_s > ma_l): return None
        if dev > args.max_dev / 100.0: return None
        # G3: 3d >= 0% AND 1d >= -1%
        if len(closes) >= 2:
            if closes[-1] / closes[-2] - 1 < -0.01: return None
        if len(closes) >= 4:
            if closes[-1] / closes[-4] - 1 < 0: return None
        return {'code': code, 'close': price, 'mom': mom, 'dev': dev}

    # Backtest
    portfolio = {}
    cash = INIT_CAPITAL
    eq_curve = []
    trades = []
    n_buys = n_sells = 0

    for fi, fri in enumerate(fridays):
        sig_date = fri.strftime('%Y-%m-%d')
        # 执行日：找下个交易日（通常是周一）
        exec_date = get_next_trading_day(fri, all_dates_sorted, direction=1)
        if exec_date is None:
            continue
        exec_ds = exec_date.strftime('%Y-%m-%d')

        # Signal at Friday
        candidates = []
        for code in all_series:
            sig = get_signal(code, sig_date)
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

        # Update HWM
        for code, pos in portfolio.items():
            p = close_at(code, exec_ds)
            if p and p > pos['hwm']:
                portfolio[code]['hwm'] = p

        # Sells
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = close_at(code, exec_ds)
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
            p = close_at(code, exec_ds) or pos['buy_price']
            cash += pos['weight'] * p
            pnl = (p / pos['buy_price'] - 1) * 100
            trades.append({'date': exec_ds, 'act': 'S', 'code': code,
                          'name': code_info.get(code, {}).get('name', ''),
                          'pnl': round(pnl, 2), 'reason': reason})
            n_sells += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_ds) or pos['buy_price'])
                          for c, pos in portfolio.items())

        # Buys
        slots = args.top_n - len(portfolio)
        if slots > 0 and equity > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            slot_val = equity / args.top_n
            for bc in buy_list[:slots]:
                exec_price = close_at(bc['code'], exec_ds)
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
                trades.append({'date': exec_ds, 'act': 'B', 'code': bc['code'],
                              'name': code_info.get(bc['code'], {}).get('name', ''),
                              'price': round(exec_price, 4)})
                n_buys += 1

        equity = cash + sum(pos['weight'] * (close_at(c, exec_ds) or pos['buy_price'])
                          for c, pos in portfolio.items())
        eq_curve.append({'date': exec_ds, 'eq': equity, 'nh': len(portfolio),
                        'holds': [code_info.get(c, {}).get('name', c) for c in portfolio]})

    # Stats
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
    if n < 2:
        print("Not enough data"); return

    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    ann_ret = ((final / init) ** (52 / n) - 1) * 100 if n > 0 else 0

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

    print(f"\n{'='*60}")
    print(f"  RESULTS: {label}")
    print(f"{'='*60}\n")
    print(f"  Period:     {fridays[0].strftime('%Y-%m-%d')} ~ {fridays[-1].strftime('%Y-%m-%d')} ({n} weeks)")
    print(f"  Total Ret:  {total_ret:+.1f}%")
    print(f"  Annual:     {ann_ret:+.1f}%")
    print(f"  Max DD:     {max_dd*100:.1f}%")
    print(f"  Sharpe:     {sharpe:.2f}")
    print(f"  Win Rate:   {win_rate:.1f}%")
    print(f"  Trades:     {n_buys}B / {n_sells}S")

    # Yearly
    print(f"\n  {'Year':<6} {'Ret':>8} {'DD':>8} {'Hold%':>7}")
    print(f"  {'-'*35}")
    from collections import defaultdict
    yg = defaultdict(list)
    for e in eq_curve:
        yr = e['date'][:4]
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
        hold_pct = statistics.mean(e['nh'] for e in yg[yr]) / args.top_n * 100
        print(f"  {yr:<6} {ret:>+7.1f}% {yearly_max_dd:>7.1f}% {hold_pct:>6.0f}%")

    # Trade summary
    if trades:
        sells = [t for t in trades if t['act'] == 'S']
        stops = [t for t in sells if t['reason'] == 'stop']
        rebals = [t for t in sells if t['reason'] == 'rebalance']
        sell_wins = sum(1 for t in sells if t['pnl'] > 0)
        print(f"\n  Trade summary:")
        print(f"  Buys: {n_buys}, Sells: {n_sells}")
        if sells:
            print(f"  Sell win rate: {sell_wins}/{len(sells)} = {sell_wins/len(sells)*100:.1f}%")
            avg_pnl = statistics.mean(t['pnl'] for t in sells)
            print(f"  Avg sell PnL: {avg_pnl:+.2f}%")
        print(f"  Stops: {len(stops)}, Rebalance: {len(rebals)}")

    # Save
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUTPUT_DIR, f'backtest_daily_{ts}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'label': label, 'params': vars(args),
            'stats': {'total_ret': total_ret, 'ann_ret': ann_ret, 'max_dd': max_dd,
                      'sharpe': sharpe, 'win_rate': win_rate,
                      'n_weeks': n, 'n_buys': n_buys, 'n_sells': n_sells},
            'equity': [{'date': e['date'], 'eq': round(e['eq'], 2)} for e in eq_curve],
            'trades': trades,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_path}")

if __name__ == '__main__':
    main()