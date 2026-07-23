#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跳过2024-W01和2025-W01（数据异常），重新跑回测"""
import json, os, sys, glob, statistics, math
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'

MA_S, MA_L, LB = 5, 21, 3
MAX_DEV, TOP_N = 15, 3
CAPITAL = 1.0
START, END = '2020-W01', '2026-W18'
MIN_MOM_3W, MIN_MOM_1W = 0.00, -0.01

def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        d = json.load(f)
    return d.get('data', d.get('etfs', []))

def load_history(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not hits:
            hits = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    d = json.load(f)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r['date'], float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        w = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        weeks[w] = cl
                    except:
                        pass
                return sorted(weeks.items())
            except:
                continue
    return None

def week_to_year(week_str):
    return int(week_str.split('-')[0])

# ── main ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    etfs = load_pool()
    all_series, code_info = {}, {}
    for etf in etfs:
        code = etf['code']
        s = load_history(code)
        if s and len(s) >= 30:
            all_series[code] = s
            code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}

    weeks_set = set()
    for s in all_series.values():
        for w, _ in s:
            weeks_set.add(w)
    valid_weeks = sorted(w for w in weeks_set if START <= w <= END)
    
    # 跳过2024-W01和2025-W01（数据异常）
    skip_weeks = {'2024-W01', '2025-W01'}
    valid_weeks = [w for w in valid_weeks if w not in skip_weeks]
    
    print(f'有效周数（跳过2024-W01, 2025-W01）: {len(valid_weeks)}')

    def closes_upto(code, week):
        return [c for w2, c in all_series.get(code, []) if w2 <= week]

    def close_at(code, week):
        for w2, c in all_series.get(code, []):
            if w2 == week:
                return c
        return None

    def get_signal(code, week):
        cs = closes_upto(code, week)
        n = len(cs)
        if n < MA_L + 1:
            return None
        price = cs[-1]
        ma_s = sum(cs[-MA_S:]) / MA_S
        ma_l = sum(cs[-MA_L:]) / MA_L
        if n <= LB:
            return None
        mom3w = cs[-1] / cs[-LB] - 1
        if mom3w <= 0 or mom3w < MIN_MOM_3W:
            return None
        if not (price > ma_s > ma_l):
            return None
        dev = price / ma_l - 1
        if dev > MAX_DEV / 100.0:
            return None
        if MIN_MOM_1W is not None and n >= 2:
            mom1w = cs[-1] / cs[-2] - 1
            if mom1w < MIN_MOM_1W:
                return None
        return {'code': code, 'close': price, 'mom': mom3w, 'dev': dev}

    portfolio = {}
    cash = CAPITAL
    eq_curve = []
    n_buys = n_sells = 0
    empty_weeks = 0

    for i in range(len(valid_weeks) - 1):
        sig_week = valid_weeks[i]
        exec_week = valid_weeks[i + 1]
        signals = [s for s in (get_signal(c, sig_week) for c in all_series) if s]
        signals.sort(key=lambda x: x['mom'], reverse=True)
        seen_cat = set()
        dedup = []
        for s in signals:
            cat = code_info.get(s['code'], {}).get('cat', '') or s['code']
            if cat not in seen_cat:
                seen_cat.add(cat)
                dedup.append(s)
        target = dedup[:TOP_N]
        target_set = {t['code'] for t in target}

        for code in list(portfolio.keys()):
            if code not in target_set:
                pr = portfolio[code]
                c = close_at(code, exec_week)
                if c:
                    cash += pr['weight'] * c / pr['buy_price']
                n_sells += 1
                del portfolio[code]

        new = [t for t in target if t['code'] not in portfolio]
        if new and cash > 0:
            w = cash / len(new)
            for t in new:
                c = close_at(t['code'], exec_week)
                if c:
                    portfolio[t['code']] = {'weight': w, 'buy_price': c, 'hwm': c}
                    cash -= w
                    n_buys += 1

        for code in list(portfolio.keys()):
            pr = portfolio[code]
            c = close_at(code, exec_week)
            if not c:
                continue
            pr['hwm'] = max(pr['hwm'], c)
            if c <= pr['buy_price'] * 0.92 or c <= pr['hwm'] * 0.90:
                cash += pr['weight'] * c / pr['buy_price']
                n_sells += 1
                del portfolio[code]

        eq = cash
        for code in portfolio:
            pr = portfolio[code]
            c = close_at(code, exec_week)
            if c:
                eq += pr['weight'] * c / pr['buy_price']
        eq_curve.append({'w': exec_week, 'eq': eq, 'nh': len(portfolio)})
        if len(portfolio) == 0:
            empty_weeks += 1

    # ── 逐年收益计算 ────────────────────────────────────────────────
    print('\n' + '=' * 70)
    print(f'  逐年收益明细（跳过2024-W01, 2025-W01）')
    print(f'  195只池 + G3条件（三周≥0% + 本周≥-1%）')
    print('=' * 70)

    yearly = {}
    for e in eq_curve:
        y = week_to_year(e['w'])
        if y not in yearly:
            yearly[y] = {'start_eq': e['eq'], 'end_eq': e['eq'], 'weeks': []}
        yearly[y]['end_eq'] = e['eq']
        yearly[y]['weeks'].append(e)

    years_sorted = sorted(yearly.keys())
    print(f'\n{"年份":>4} {"起始权益":>10} {"结束权益":>10} {"收益率":>8} '
          f'{"年化收益":>8} {"周数":>4}')
    print('-' * 60)

    for y in years_sorted:
        data = yearly[y]
        start_eq = data['start_eq']
        end_eq = data['end_eq']
        ret = (end_eq / start_eq - 1) * 100
        n_weeks = len(data['weeks'])
        ann_ret = ((end_eq / start_eq) ** (52.0 / n_weeks) - 1) * 100

        print(f'{y:>4} {start_eq:>10.4f} {end_eq:>10.4f} {ret:>+7.1f}% {ann_ret:>+7.1f}% {n_weeks:>4}')

    # 汇总
    print('-' * 60)
    eq0 = eq_curve[0]['eq']
    eqT = eq_curve[-1]['eq']
    total_ret = (eqT / eq0 - 1) * 100
    years_span = len(eq_curve) / 52.0
    ann_ret = ((eqT / eq0) ** (1.0 / years_span) - 1) * 100

    peak_all = eq_curve[0]['eq']
    max_dd_all = 0.0
    for e in eq_curve:
        if e['eq'] > peak_all:
            peak_all = e['eq']
        dd = (peak_all - e['eq']) / peak_all
        if dd > max_dd_all:
            max_dd_all = dd

    returns = []
    for i in range(1, len(eq_curve)):
        r = (eq_curve[i]['eq'] / eq_curve[i-1]['eq']) - 1
        returns.append(r)
    mu = statistics.mean(returns)
    sigma = statistics.stdev(returns)
    sharpe = (mu / sigma) * math.sqrt(52) if sigma > 0 else 0.0
    win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0

    print(f'\n汇总:')
    print(f'  总收益:   {total_ret:+.1f}%')
    print(f'  年化收益: {ann_ret:+.1f}%')
    print(f'  最大回撤: {max_dd_all*100:.1f}%')
    print(f'  夏普:     {sharpe:.2f}')
    print(f'  胜率:     {win_rate:.1f}%')

    # 保存结果
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT_DIR, f'bt_G3_SKIP_2024W01_2025W01_{ts}.json')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({
            'yearly': {str(y): {
                'start_eq': yearly[y]['start_eq'],
                'end_eq': yearly[y]['end_eq'],
                'ret': (yearly[y]['end_eq'] / yearly[y]['start_eq'] - 1) * 100,
                'ann_ret': ((yearly[y]['end_eq'] / yearly[y]['start_eq']) ** (52.0 / len(yearly[y]['weeks'])) - 1) * 100,
            } for y in years_sorted},
            'summary': {
                'total_ret': total_ret,
                'ann_ret': ann_ret,
                'max_dd': max_dd_all * 100,
                'sharpe': sharpe,
            },
        }, f, ensure_ascii=False, indent=2)
    print(f'\n保存: {out}')
