#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.0 市场状态过滤回测对比
测试6种市场过滤条件，输出对比表
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

MA_S = 5
MA_L = 21
LB = 3
MAX_DEV = 15
TOP_N = 3
CAPITAL = 1.0
START = '2020-W01'
END = '2026-W18'

INDEX_CODES = {
    'cyb': '399006',
    'hs300': '000300',
}

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
                    d = json.load(f)
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
                        weeks[f'{y}-W{w:02d}'] = cl
                    except:
                        pass
                return sorted(weeks.items())
            except:
                continue
    return None

def calc_sharpe(returns):
    if not returns or len(returns) < 2:
        return 0
    mu = statistics.mean(returns)
    sigma = statistics.stdev(returns) if len(returns) > 1 else 0
    if sigma == 0:
        return 0
    return (mu / sigma) * (52 ** 0.5)

def backtest_with_filter(filter_name, filter_func, index_data, all_weeks_list):
    """
    执行回测。
    filter_func(sig_week, index_data) -> bool
    """
    etfs = load_pool()
    all_series = {}
    code_info = {}
    for etf in etfs:
        code = etf['code']
        s = load_history(code)
        if s and len(s) >= 30:
            all_series[code] = s
            code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}

    weeks_set = set()
    for s in all_series.values():
        for w, c in s:
            weeks_set.add(w)
    valid_weeks = sorted(w for w in weeks_set if START <= w <= END)

    def get_signal(code, week):
        cs = [c for w2, c in all_series.get(code, []) if w2 <= week]
        n = len(cs)
        if n < MA_L + 1:
            return None
        price = cs[-1]
        ma_s = sum(cs[-MA_S:]) / MA_S
        ma_l = sum(cs[-MA_L:]) / MA_L
        mom = cs[-1] / cs[-LB] - 1 if n > LB else None
        dev = price / ma_l - 1
        if mom is None or mom <= 0:
            return None
        if not (price > ma_s > ma_l):
            return None
        if dev > MAX_DEV / 100.0:
            return None
        return {'code': code, 'close': price, 'mom': mom, 'dev': dev}

    def close_at(code, week):
        for w2, c in all_series.get(code, []):
            if w2 == week:
                return c
        return None

    portfolio = {}
    cash = CAPITAL
    eq_curve = []
    n_buys = n_sells = 0
    empty_weeks = 0
    total_weeks = 0

    for i in range(len(valid_weeks) - 1):
        sig_week = valid_weeks[i]
        exec_week = valid_weeks[i + 1]
        total_weeks += 1

        market_ok = filter_func(sig_week, index_data)

        if not market_ok:
            empty_weeks += 1
            for code in list(portfolio.keys()):
                c = close_at(code, exec_week)
                if c:
                    pr = portfolio[code]
                    cash += pr['weight'] * c / pr['buy_price']
                n_sells += 1
            portfolio = {}
            eq_curve.append({'w': exec_week, 'eq': cash, 'nh': 0})
            continue

        # 选股
        signals = []
        for code in all_series:
            sig = get_signal(code, sig_week)
            if sig:
                signals.append(sig)

        signals.sort(key=lambda x: x['mom'], reverse=True)
        cats = set()
        dedup = []
        for s in signals:
            c = code_info.get(s['code'], {}).get('cat', '') or s['code']
            if c not in cats:
                cats.add(c)
                dedup.append(s)

        target = dedup[:TOP_N]
        target_codes = {t['code'] for t in target}

        # 卖出
        for code in list(portfolio.keys()):
            if code not in target_codes:
                pr = portfolio[code]
                c = close_at(code, exec_week)
                if c:
                    cash += pr['weight'] * c / pr['buy_price']
                n_sells += 1
                del portfolio[code]

        # 买入
        new_codes = [t for t in target if t['code'] not in portfolio]
        if new_codes and cash > 0:
            w = cash / len(new_codes)
            for t in new_codes:
                c = close_at(t['code'], exec_week)
                if c:
                    portfolio[t['code']] = {'weight': w, 'buy_price': c, 'hwm': c}
                    cash -= w
                    n_buys += 1

        # 止损
        for code in list(portfolio.keys()):
            pr = portfolio[code]
            c = close_at(code, exec_week)
            if c:
                pr['hwm'] = max(pr['hwm'], c)
                if c <= pr['buy_price'] * 0.92 or c <= pr['hwm'] * 0.90:
                    cash += pr['weight'] * c / pr['buy_price']
                    n_sells += 1
                    del portfolio[code]

        # 权益
        eq = cash
        for code in portfolio:
            pr = portfolio[code]
            c = close_at(code, exec_week)
            if c:
                eq += pr['weight'] * c / pr['buy_price']
        eq_curve.append({'w': exec_week, 'eq': eq, 'nh': len(portfolio)})

    if not eq_curve:
        return None

    eq0 = eq_curve[0]['eq']
    eqT = eq_curve[-1]['eq']
    total_ret = (eqT / eq0 - 1) * 100
    n_weeks = len(eq_curve)
    years = n_weeks / 52.0
    ann_ret = ((eqT / eq0) ** (1.0 / years) - 1) * 100 if years > 0 else 0

    peak = eq_curve[0]['eq']
    max_dd = 0
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
    sharpe = calc_sharpe(returns)
    calmar = ann_ret / (max_dd * 100) if max_dd > 0 else 0
    win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0

    return {
        'filter': filter_name,
        'total_ret': total_ret,
        'ann_ret': ann_ret,
        'max_dd': max_dd * 100,
        'sharpe': sharpe,
        'calmar': calmar,
        'win_rate': win_rate,
        'n_buys': n_buys,
        'n_sells': n_sells,
        'empty_pct': empty_weeks / total_weeks * 100 if total_weeks > 0 else 0,
        'n_weeks': n_weeks,
    }

def get_index_mom_3w(idx_name, week, index_data):
    """计算指数3周动量（百分比）"""
    d = index_data.get(idx_name, {})
    weeks_sorted = sorted(d.keys())
    if week not in d:
        return None
    now_close = d[week]
    try:
        now_idx = weeks_sorted.index(week)
    except ValueError:
        return None
    if now_idx < 3:
        return None
    past_close = d[weeks_sorted[now_idx - 3]]
    return (now_close / past_close - 1) * 100

# ========== 主程序 ==========
if __name__ == '__main__':
    print(f"{'='*70}")
    print(f"  市场状态过滤回测对比")
    print(f"  策略: MA{MA_S}/{MA_L} LB={LB} D{MAX_DEV} H{TOP_N}")
    print(f"  区间: {START} ~ {END}")
    print(f"{'='*70}\n")

    # 加载指数数据
    index_data = {}
    for idx_name, idx_code in INDEX_CODES.items():
        s = load_history(idx_code)
        if s:
            index_data[idx_name] = dict(s)
            print(f"  指数 {idx_name} ({idx_code}): {len(s)} 周")
        else:
            print(f"  指数 {idx_name} ({idx_code}): 加载失败")

    # 构建周列表（用于回测）
    etfs = load_pool()
    all_series_tmp = {}
    for etf in etfs:
        code = etf['code']
        s = load_history(code)
        if s and len(s) >= 30:
            all_series_tmp[code] = s
    weeks_set = set()
    for s in all_series_tmp.values():
        for w, c in s:
            weeks_set.add(w)
    all_weeks_list = sorted(w for w in weeks_set if START <= w <= END)

    # 过滤函数
    filters = [
        ('A: 无过滤（基准）', lambda w, idx: True),
        ('B: 创业板指3周动量 > 0%', lambda w, idx: get_index_mom_3w('cyb', w, idx) is not None and get_index_mom_3w('cyb', w, idx) > 0),
        ('C: 创业板指3周动量 > -3%', lambda w, idx: get_index_mom_3w('cyb', w, idx) is not None and get_index_mom_3w('cyb', w, idx) > -3),
        ('D: 创业板指3周动量 > -5%', lambda w, idx: get_index_mom_3w('cyb', w, idx) is not None and get_index_mom_3w('cyb', w, idx) > -5),
        ('E: 沪深300 3周动量 > 0%', lambda w, idx: get_index_mom_3w('hs300', w, idx) is not None and get_index_mom_3w('hs300', w, idx) > 0),
        ('F: 创业板+沪深300 同时 > -3%', lambda w, idx: (
            get_index_mom_3w('cyb', w, idx) is not None and get_index_mom_3w('cyb', w, idx) > -3 and
            get_index_mom_3w('hs300', w, idx) is not None and get_index_mom_3w('hs300', w, idx) > -3
        )),
    ]

    results = []
    for name, func in filters:
        print(f"\n{'─'*60}")
        print(f"  回测: {name}")
        print(f"{'─'*60}")
        r = backtest_with_filter(name, func, index_data, all_weeks_list)
        if r:
            results.append(r)
            print(f"  完成: 年化={r['ann_ret']:+.1f}%  回撤={r['max_dd']:.1f}%  夏普={r['sharpe']:.2f}  空仓={r['empty_pct']:.0f}%")
        else:
            print("  回测失败")

    # 对比表
    print(f"\n{'='*70}")
    print(f"  回测对比结果")
    print(f"{'='*70}")
    print(f"{'过滤条件':<35} {'年化':>7} {'回撤':>7} {'夏普':>6} {'空仓':>6}")
    print('─' * 70)
    # 按夏普排序
    results.sort(key=lambda x: x['sharpe'], reverse=True)
    for r in results:
        print(f"{r['filter']:<35} {r['ann_ret']:>+6.1f}% {r['max_dd']:>6.1f}% {r['sharpe']:>5.2f} {r['empty_pct']:>5.0f}%")

    # 保存
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT_DIR, f'bt_filter_compare_{ts}.json')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {out}")
