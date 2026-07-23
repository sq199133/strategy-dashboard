# -*- coding: utf-8 -*-
"""批量回测v2：修复detect_patterns中的周列表bug"""
import sys, os, json, glob, argparse, statistics
from datetime import datetime as dt
from collections import defaultdict

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR  = r'D:\QClaw_Trading\review'
DEF_MAX_DEV = 15.0
DEF_TOP_N   = 3
DEF_LB      = 3
DEF_ATR_F   = 0.85
DEF_SC_W1   = 0.40
DEF_SC_W3   = 0.40
DEF_SC_W8   = 0.20
DEF_CAPITAL = 100000.0

def load_etf_data(etfs):
    series = {}
    ohlc   = {}
    weeks_set = set()
    for etf in etfs:
        code = etf['code']
        for pat in [code, f'sh{code}', f'sz{code}', code[2:]]:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
            if not matches:
                matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}.json'))
            if matches:
                try:
                    with open(matches[0], encoding='utf-8') as f:
                        raw = f.read().replace('NaN', 'null')
                    d = json.loads(raw)
                    recs = d.get('records', []) if isinstance(d, dict) else d
                    if not recs:
                        break
                    if isinstance(recs[0], list):
                        recs = [{'date': r[0], 'open': r[1], 'high': r[2],
                                 'low': r[3], 'close': r[4], 'vol': r[5]}
                                for r in recs]
                    elif 'w' in recs[0]:
                        recs = [{'date': r.get('date', ''), 'open': r.get('open', r['close']),
                                 'high': r.get('high', r['close']), 'low': r.get('low', r['close']),
                                 'close': r['close'], 'vol': r.get('vol', 0)}
                                for r in recs]
                    weeks = {}
                    for r in recs:
                        ds = r.get('date', '')
                        if not ds:
                            continue
                        try:
                            y, wn, _ = dt.strptime(ds, '%Y-%m-%d').isocalendar()
                            wk = f'{y}-W{wn:02d}'
                            if wk not in weeks or ds > weeks[wk][0]:
                                weeks[wk] = (ds, r['close'], r.get('open', r['close']),
                                             r.get('high', r['close']), r.get('low', r['close']),
                                             r.get('vol', 0))
                        except:
                            pass
                    if not weeks:
                        break
                    sorted_wks = sorted(weeks.items())
                    series[code] = [(wk, cl) for wk, (_, cl, *_) in sorted_wks]
                    ohlc[code] = {wk: {'o': op, 'h': hi, 'l': lo, 'c': cl, 'v': vo}
                                  for wk, (_, cl, op, hi, lo, vo) in sorted_wks}
                    weeks_set.update(wk for wk, _ in sorted_wks)
                except:
                    pass
    return series, ohlc, sorted(weeks_set)

def compute_atr(ohlc, all_weeks):
    all_atr = {}
    for code, weeks_dict in ohlc.items():
        if len(weeks_dict) < 30:
            continue
        wk_list = sorted(weeks_dict.keys())
        price_wk = {wk: weeks_dict[wk]['c'] for wk in wk_list}
        trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur = weeks_dict[wk_list[i]]
            prv = weeks_dict[wk_list[i-1]]
            h, l  = cur['h'], cur['l']
            pc    = prv['c']
            trs[i] = max(h - l, abs(h - pc), abs(l - pc))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:]) / 14
                slow = sum(vals) / 21
                if slow > 0:
                    atrs[wk_list[i]] = fast / slow
        all_atr[code] = atrs
    return all_atr

def detect_patterns_v2(ohlc_code, wk_list, idx):
    """
    修复版：使用ETF自身的周列表(wk_list)和索引(idx)
    wk_list: ETF自身的周列表（已排序）
    idx: 当前周在wk_list中的索引（>=21）
    """
    if idx < 21:
        return False, False
    
    # 获取当前周+前2周数据
    w0 = ohlc_code.get(wk_list[idx], {})
    w1 = ohlc_code.get(wk_list[idx-1], {}) if idx >= 1 else {}
    w2 = ohlc_code.get(wk_list[idx-2], {}) if idx >= 2 else {}
    
    for w in [w0, w1, w2]:
        if not w or None in [w.get('c'), w.get('o'), w.get('h'), w.get('l')]:
            return False, False
    
    ci, oi, hi, li = w0['c'], w0['o'], w0['h'], w0['l']
    vi = w0.get('v', 0)
    
    body     = abs(ci - oi)
    u_shadow = hi - max(ci, oi)
    l_shadow = min(ci, oi) - li
    s2b      = u_shadow / body if body > 0 else 99
    
    # 10周均量
    vol_valid = []
    for j in range(max(0, idx-9), idx+1):
        v = ohlc_code.get(wk_list[j], {}).get('v', 0)
        if v and v > 0:
            vol_valid.append(v)
    avg_vol10 = sum(vol_valid) / len(vol_valid) if vol_valid else 1
    vol_r = vi / avg_vol10 if avg_vol10 > 0 else 1
    
    # 20周涨幅
    if idx >= 20:
        prev20_c = ohlc_code.get(wk_list[idx-20], {}).get('c')
        gain20w = (ci / prev20_c - 1) if prev20_c and prev20_c > 0 else 0
    else:
        gain20w = 0
    
    # MA5/MA21
    ma5_list = [ohlc_code.get(wk_list[j], {}).get('c') for j in range(max(0, idx-4), idx+1)]
    ma21_list = [ohlc_code.get(wk_list[j], {}).get('c') for j in range(max(0, idx-20), idx+1)]
    if None in ma5_list or None in ma21_list:
        return False, False
    ma5 = sum(ma5_list) / len(ma5_list)
    ma21 = sum(ma21_list) / len(ma21_list)
    if ma21 == 0:
        return False, False
    
    # ---- C型仙人指路 ----
    c_pattern = (
        ci > oi
        and s2b > 1.0
        and l_shadow < body * 0.5
        and vol_r < 1.5
        and ci > ma5 > ma21
        and gain20w < 0.5
    )
    
    # ---- B1型红三兵 ----
    b1_ok = False
    if idx >= 2:
        o_prev = [ohlc_code.get(wk_list[j], {}).get('o') for j in range(idx-2, idx+1)]
        c_prev = [ohlc_code.get(wk_list[j], {}).get('c') for j in range(idx-2, idx+1)]
        l_prev = [ohlc_code.get(wk_list[j], {}).get('l') for j in range(idx-2, idx+1)]
        v_prev = [ohlc_code.get(wk_list[j], {}).get('v', 0) for j in range(idx-2, idx+1)]
        if None not in o_prev and None not in c_prev and None not in l_prev and None not in v_prev:
            w1_b  = c_prev[0] > o_prev[0]
            w2_b  = c_prev[1] > o_prev[1]
            w3_b  = ci > oi
            w1_up = l_prev[1] > l_prev[0] * 0.98
            vol_ok = all(v < avg_vol10 * 1.5 for v in v_prev)
            b1_ok = w1_b and w2_b and w3_b and w1_up and vol_ok
    
    return c_pattern, b1_ok

def run_backtest(c_bonus, b1_bonus, data_cache=None):
    if data_cache is None:
        with open(POOL_FILE, encoding='utf-8') as f:
            pool_data = json.load(f)
        etfs = pool_data if isinstance(pool_data, list) else pool_data.get('data', [])
        series, ohlc, all_weeks = load_etf_data(etfs)
        all_atr  = compute_atr(ohlc, all_weeks)
        code_cat = {e['code']: e.get('category', '') or '' for e in etfs}
        data_cache = (series, all_atr, all_weeks, code_cat, ohlc)
    else:
        series, all_atr, all_weeks, code_cat, ohlc = data_cache
    
    if not series:
        print("ERROR: no data loaded"); return None
    
    ma_l = 21
    first_avail = {}
    for c, s in series.items():
        if len(s) >= ma_l + 1:
            first_avail[c] = s[ma_l][0]
        else:
            first_avail[c] = None
    
    n_weeks = len(all_weeks) - 1
    if n_weeks < 10:
        print("ERROR: not enough weeks"); return None
    
    # Limit to 2014-2026
    _MIN_YR, _MAX_YR = 2014, 2026
    _si_start = 0
    for _i, _wk in enumerate(all_weeks):
        if int(_wk[:4]) >= _MIN_YR:
            _si_start = max(0, _i - 1); break
    _si_end = n_weeks
    
    # For pattern detection, we need each ETF's own week list
    # Build: code -> sorted list of weeks
    code_wklist = {c: [wk for wk, _ in s] for c, s in series.items()}
    
    portfolio = {}; cash = DEF_CAPITAL; eq_curve = []; n_buys = n_sells = 0
    
    for si in range(_si_start, _si_end):
        sig_week  = all_weeks[si]
        exec_week = all_weeks[si + 1]
        
        candidates = []
        for code, s in series.items():
            if first_avail.get(code) and first_avail[code] > sig_week:
                continue
            idx = None
            for j, (wk, _) in enumerate(s):
                if wk == sig_week:
                    idx = j; break
            if idx is None or idx < 21:
                continue
            
            price = s[idx][1]
            if price is None or price <= 0:
                continue
            
            ma5_list  = [s[j][1] for j in range(idx-4, idx+1)]
            ma21_list = [s[j][1] for j in range(idx-20, idx+1)]
            if None in ma5_list or None in ma21_list:
                continue
            ma5  = sum(ma5_list) / 5
            ma21 = sum(ma21_list) / 21
            if ma21 == 0:
                continue
            
            dev = abs(price / ma21 - 1) * 100
            if dev > DEF_MAX_DEV:
                continue
            
            mom     = s[idx][1] / s[idx-DEF_LB][1] - 1
            mom1w_v = s[idx][1] / s[idx-1][1] - 1 if idx >= 1 else mom
            mom8w_v = s[idx][1] / s[idx-8][1] - 1 if idx >= 8 else mom
            score   = DEF_SC_W1 * mom1w_v + DEF_SC_W3 * mom + DEF_SC_W8 * mom8w_v
            
            ar = all_atr.get(code, {}).get(sig_week)
            if ar is not None and ar < DEF_ATR_F:
                continue
            
            # 使用修复版detect_patterns
            wk_list = code_wklist.get(code, [])
            c_pat, b1_pat = detect_patterns_v2(ohlc.get(code, {}), wk_list, idx)
            
            candidates.append({
                'code': code, 'close': price,
                'score': score, 'dev': dev, 'ma5': ma5, 'ma21': ma21,
                'c_pattern': c_pat, 'b1_pattern': b1_pat,
            })
        
        for c in candidates:
            adj = c['score']
            if c_bonus > 0 and c.get('c_pattern'):
                adj += c_bonus
            if b1_bonus > 0 and c.get('b1_pattern'):
                adj += b1_bonus
            c['_adj'] = adj
        
        candidates.sort(key=lambda x: x['_adj'], reverse=True)
        
        cats = set()
        target = []
        for c in candidates:
            cat = code_cat.get(c['code'], '')
            if cat not in cats:
                cats.add(cat)
                target.append(c)
        target = target[:DEF_TOP_N]
        target_codes = {t['code'] for t in target}
        
        for code in list(portfolio.keys()):
            p = None
            for wk, cl in series[code]:
                if wk == sig_week:
                    p = cl; break
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p
        
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = None
            for wk, cl in series[code]:
                if wk == sig_week:
                    p = cl; break
            if p is None:
                to_sell.append((code, 'nodata')); continue
            cost_pnl = p / pos['buy_price'] - 1
            hwm_pnl  = p / pos['hwm'] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, 'stop'))
            elif code not in target_codes:
                to_sell.append((code, 'rebalance'))
        
        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = None
            for wk, cl in series[code]:
                if wk == sig_week:
                    p = cl; break
            cash += pos['weight'] * (p or pos['buy_price'])
            n_sells += 1
        
        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            slot_val = (cash + sum(pos['weight'] * pos['buy_price'] for pos in portfolio.values())) / DEF_TOP_N
            for bc in buy_list[:slots]:
                p_exec = None
                for wk, cl in series[bc['code']]:
                    if wk == sig_week:
                        p_exec = cl; break
                if p_exec is None or p_exec <= 0:
                    continue
                weight = slot_val / p_exec
                cost   = weight * p_exec
                if cost > cash * 0.98:
                    weight = cash * 0.98 / p_exec
                    cost   = weight * p_exec
                if weight <= 0:
                    break
                cash -= cost
                portfolio[bc['code']] = {'weight': weight, 'buy_price': p_exec, 'hwm': p_exec}
                n_buys += 1
        
        equity = cash + sum(
            pos['weight'] * (next((cl for wk, cl in series[c] if wk == exec_week), pos['buy_price']))
            for c, pos in portfolio.items()
        )
        eq_curve.append({'w': exec_week, 'eq': equity, 'nh': len(portfolio),
                         'h': list(portfolio.keys())})
    
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
    if n < 2:
        return None
    
    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    years = n / 52
    ann_ret = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    peak = eqs[0]
    max_dd = 0
    for eq in eqs:
        if eq > peak:
            peak = eq
        dd = eq / peak - 1
        if dd < max_dd:
            max_dd = dd
    
    w_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
    if w_rets:
        avg_w = statistics.mean(w_rets)
        std_w = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52**0.5) if std_w > 0 else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = win_rate = 0
    
    yg = defaultdict(list)
    for e in eq_curve:
        yg[e['w'][:4]].append(e)
    yearly = {}
    for yr in sorted(yg):
        es = [e['eq'] for e in yg[yr]]
        if not es or es[0] <= 0:
            continue
        ret = (es[-1] / es[0] - 1) * 100
        pk = es[0]
        yr_dd = 0
        for eq in es:
            if eq > pk:
                pk = eq
            dd = (eq / pk - 1) * 100
            if dd < yr_dd:
                yr_dd = dd
        yearly[yr] = {'ret': ret, 'dd': yr_dd}
    
    return {
        'c_bonus': c_bonus, 'b1_bonus': b1_bonus,
        'ann_ret': ann_ret, 'total_ret': total_ret,
        'max_dd': max_dd * 100, 'sharpe': sharpe,
        'win_rate': win_rate, 'n_buys': n_buys, 'n_sells': n_sells,
        'years': years, 'n_weeks': n, 'yearly': yearly,
    }

def main():
    import time
    print("\n" + "="*70)
    print("  PATTERN BONUS BATCH BACKTEST v2 (Fixed detect_patterns)")
    print("="*70)
    
    print("\n[Data] Loading once...")
    with open(POOL_FILE, encoding='utf-8') as f:
        pool_data = json.load(f)
    etfs = pool_data if isinstance(pool_data, list) else pool_data.get('data', [])
    series, ohlc, all_weeks = load_etf_data(etfs)
    all_atr  = compute_atr(ohlc, all_weeks)
    code_cat = {e['code']: e.get('category', '') or '' for e in etfs}
    print(f"    {len(series)} ETFs, {len(all_weeks)} weeks")
    data_cache = (series, all_atr, all_weeks, code_cat, ohlc)
    
    configs = [(0, 0)]
    for c in [0.02, 0.05, 0.08, 0.10, 0.15, 0.20]:
        configs.append((c, 0))
    for b1 in [0.02, 0.03, 0.05]:
        configs.append((0, b1))
    for c in [0.05, 0.10, 0.15]:
        for b1 in [0.03, 0.05]:
            configs.append((c, b1))
    seen = set()
    unique = []
    for c in configs:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    configs = unique
    
    results = []
    for idx, (c_b, b1_b) in enumerate(configs):
        lbl = f"C+{c_b:.2f} B1+{b1_b:.2f}" if c_b > 0 or b1_b > 0 else "基线(无加分)"
        print(f"  [{idx+1:02d}/{len(configs)}] {lbl:20s}", end='', flush=True)
        r = run_backtest(c_b, b1_b, data_cache)
        if r:
            dA = r['ann_ret'] - (results[0]['ann_ret'] if results else 0)
            dS = r['sharpe'] - (results[0]['sharpe'] if results else 0)
            print(f" Ann={r['ann_ret']:+.2f}% DD={r['max_dd']:5.1f}% Sharpe={r['sharpe']:.3f} dA={dA:+.2f} dS={dS:+.3f}")
            results.append(r)
        else:
            print(" FAILED")
    
    baseline = results[0]
    print("\n\n" + "="*95)
    print("  SUMMARY (v2 Fixed)")
    print("  Baseline: Ann={:.2f}% DD={:.1f}% Sharpe={:.3f}".format(
          baseline['ann_ret'], baseline['max_dd'], baseline['sharpe']))
    print("="*95)
    print(f"\n  {'C':>5}  {'B1':>5}  {'Ann.Ret':>8}  {'MaxDD':>7}  {'Sharpe':>7}  {'WinR':>6}  {'dAnn':>6}  {'dSh':>6}")
    print(f"  {'-'*75}")
    BL_A = baseline['ann_ret']; BL_S = baseline['sharpe']
    for r in results:
        dA = r['ann_ret']-BL_A; dS = r['sharpe']-BL_S
        print(f"  {r['c_bonus']:>5.2f}  {r['b1_bonus']:>5.2f}  {r['ann_ret']:>+8.2f}%  {r['max_dd']:>6.1f}%  "
              f"{r['sharpe']:>7.3f}  {r['win_rate']:>6.1f}%  {dA:>+6.2f}  {dS:>+6.3f}")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT_DIR, f'pattern_bonus_batch_v2_{ts}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'baseline': baseline, 'results': results}, f, ensure_ascii=False, indent=2)
    print(f"\n\nSaved: {out}")

if __name__ == '__main__':
    main()
