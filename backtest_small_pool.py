#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标的池缩小回测：只用用户指定的ETF代码
+ G3最优过滤条件（三周≥0% + 本周≥-1%）
"""
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

# 用户指定的标的池（从图片提取）
USER_CODES = [
    '159611','515920','513850','159687','161130','562500','588200',
    '159786','159108','501312','517850','561500','589600','588220',
    '515580','162415','563010','160140','513400','159625','588010',
    '159617','512870','562010','512390','510770','562330','511380',
    '160719','501225','161116','160216','159819','159949','512100',
    '560860','588170','516160','159851','512950','515300','510810',
    '563230','512200','563300','516570','516970','159667','159638',
    '560570','159141','512330','562520','588850','512260','159822',
    '159980','501018','520580','520830','159985','161815','160125',
    '162411','513080','510300','510500','512890','159870','159995',
    '159852','159561','160644','515450','159869','515100','510900',
    '513070','560710','515400','161127','562060','589720','588830',
    '159745','159698','515150','515750','510170','159107','159572',
    '588700','510160','159328','159725','159918','515590',
]

def load_pool():
    """加载全量池，但只保留用户指定的代码"""
    with open(POOL_FILE, encoding='utf-8') as f:
        d = json.load(f)
    all_etfs = d.get('data', d.get('etfs', []))
    # 只保留用户指定的代码
    user_set = set(USER_CODES)
    filtered = [e for e in all_etfs if e.get('code', '') in user_set]
    print(f'全量池: {len(all_etfs)} 只 -> 用户指定: {len(filtered)} 只')
    return filtered

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

def run_backtest(min_mom3w=0.0, min_mom1w=None):
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
        if mom3w <= 0:
            return None
        if not (price > ma_s > ma_l):
            return None
        dev = price / ma_l - 1
        if dev > MAX_DEV / 100.0:
            return None
        if mom3w < min_mom3w:
            return None
        if min_mom1w is not None:
            if n < 2:
                return None
            mom1w = cs[-1] / cs[-2] - 1
            if mom1w < min_mom1w:
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

    if not eq_curve:
        return None

    eq0, eqT = eq_curve[0]['eq'], eq_curve[-1]['eq']
    total_ret = (eqT / eq0 - 1) * 100
    years = len(eq_curve) / 52.0
    ann_ret = ((eqT / eq0) ** (1.0 / years) - 1) * 100 if years > 0 else 0

    peak = eq_curve[0]['eq']
    max_dd = 0.0
    for e in eq_curve:
        if e['eq'] > peak:
            peak = e['eq']
        dd = (peak - e['eq']) / peak
        if dd > max_dd:
            max_dd = dd

    returns = []
    for i in range(1, len(eq_curve)):
        r = (eq_curve[i]['eq'] / eq_curve[i-1]['eq']) - 1
        returns.append(r)

    if len(returns) >= 2:
        mu = statistics.mean(returns)
        sigma = statistics.stdev(returns)
        sharpe = (mu / sigma) * math.sqrt(52) if sigma > 0 else 0.0
    else:
        sharpe = 0.0
    win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0

    return {
        'total_ret': total_ret, 'ann_ret': ann_ret, 'max_dd': max_dd * 100,
        'sharpe': sharpe, 'calmar': ann_ret / (max_dd * 100) if max_dd > 0 else 0,
        'win_rate': win_rate, 'n_buys': n_buys, 'n_sells': n_sells,
        'empty_pct': empty_weeks / len(eq_curve) * 100, 'n_weeks': len(eq_curve),
    }

# ── main ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 70)
    print(f'  缩小标的池回测（{len(USER_CODES)}只指定ETF）')
    print(f'  策略: MA{MA_S}/{MA_L} LB={LB} D{MAX_DEV} H{TOP_N}')
    print(f'  区间: {START} ~ {END}')
    print('=' * 70)

    # 测试G3最优条件 + 基准
    cases = [
        ('缩小池-无过滤（基准）',           0.00,  None),
        ('缩小池-G3: 三周≥0%+本周≥-1%',   0.00, -0.01),
        ('缩小池-G1: 三周≥0%+本周≥0%',    0.00,  0.00),
        ('缩小池-G8: 三周≥5%+本周≥-1%',   0.05, -0.01),
        ('缩小池-G9: 三周≥5%+本周≥0%',    0.05,  0.00),
        ('缩小池-G10: 三周≥10%+本周≥-1%', 0.10, -0.01),
    ]

    results = []
    for label, m3, m1 in cases:
        tag3 = '>0%' if m3 == 0 else f'{m3*100:+.0f}%'
        tag1 = '不限' if m1 is None else (f'{m1*100:+.0f}%' if m1 != 0 else '>0%')
        print(f'\n{"─"*60}')
        print(f'  {label}')
        print(f'  三周阈值: {tag3}   本周阈值: {tag1}')
        print(f'{"─"*60}')
        r = run_backtest(min_mom3w=m3, min_mom1w=m1)
        if r:
            results.append((label, r))
            print(f'  年化: {r["ann_ret"]:+.1f}%  回撤: {r["max_dd"]:.1f}%  '
                  f'夏普: {r["sharpe"]:.2f}  空仓: {r["empty_pct"]:.0f}%')
        else:
            print('  回测失败')

    results.sort(key=lambda x: x[1]['sharpe'], reverse=True)
    print(f'\n{"="*70}')
    print(f'  缩小池回测结果（按夏普排序）')
    print(f'{"="*70}')
    print(f'{"条件":<38} {"年化":>7} {"回撤":>7} {"夏普":>6} {"空仓":>5}')
    print('─' * 72)
    for label, r in results:
        print(f'{label:<38} {r["ann_ret"]:>+6.1f}% {r["max_dd"]:>6.1f}% {r["sharpe"]:>5.2f} {r["empty_pct"]:>4.0f}%')

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT_DIR, f'bt_small_pool_{ts}.json')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump([{'label': lb, **r} for lb, r in results], f, ensure_ascii=False, indent=2)
    print(f'\n保存: {out}')
