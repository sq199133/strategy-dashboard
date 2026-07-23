# -*- coding: utf-8 -*-
"""回测高量能惩罚因子（量比>阈值时罚分或跳过）"""
import sys, os, json, glob, statistics
from datetime import datetime as dt
from collections import defaultdict

HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'
POOL_FILE   = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'
OUTPUT_DIR  = r'D:\Qclaw_Trading\review'
DEF_MAX_DEV = 15.0
DEF_TOP_N   = 3
DEF_LB      = 3
DEF_ATR_F   = 0.85
DEF_SC_W1   = 0.40
DEF_SC_W3   = 0.40
DEF_SC_W8   = 0.20
C_BONUS     = 0.02
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
                    if not recs: break
                    if isinstance(recs[0], list):
                        recs = [{'date': r[0], 'close': r[4], 'vol': r[5]} for r in recs]
                    elif 'w' in recs[0]:
                        recs = [{'date': r.get('date', ''), 'close': r['close'], 'vol': r.get('vol', 0)} for r in recs]
                    weeks = {}
                    for r in recs:
                        ds = r.get('date', '')
                        if not ds: continue
                        try:
                            y, wn, _ = dt.strptime(ds, '%Y-%m-%d').isocalendar()
                            wk = f'{y}-W{wn:02d}'
                            if wk not in weeks or ds > weeks[wk][0]:
                                weeks[wk] = (ds, r['close'], r.get('vol', 0))
                        except: pass
                    if not weeks: break
                    sorted_wks = sorted(weeks.items())
                    series[code] = [(wk, cl) for wk, (_, cl, *_) in sorted_wks]
                    ohlc[code] = {wk: {'c': cl, 'v': vo} for wk, (_, cl, vo) in sorted_wks}
                    weeks_set.update(wk for wk, _ in sorted_wks)
                except: pass
    return series, ohlc, sorted(weeks_set)

def compute_atr(ohlc, all_weeks):
    all_atr = {}
    for code, weeks_dict in ohlc.items():
        if len(weeks_dict) < 30: continue
        wk_list = sorted(weeks_dict.keys())
        trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur, prv = weeks_dict[wk_list[i]], weeks_dict[wk_list[i-1]]
            h, l, pc = cur.get('h', cur['c']), cur.get('l', cur['c']), prv['c']
            trs[i] = max(h - l, abs(h - pc), abs(l - pc))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:]) / 14
                slow = sum(vals) / 21
                if slow > 0: atrs[wk_list[i]] = fast / slow
        all_atr[code] = atrs
    return all_atr

def detect_patterns_v2(ohlc_code, wk_list, idx):
    if idx < 21: return False
    w0 = ohlc_code.get(wk_list[idx], {})
    if not w0 or None in [w0.get('c'), w0.get('o'), w0.get('h'), w0.get('l')]:
        return False
    ci, oi, hi, li = w0['c'], w0['o'], w0['h'], w0['l']
    body = abs(ci - oi)
    u_shadow = hi - max(ci, oi)
    l_shadow = min(ci, oi) - li
    s2b = u_shadow / body if body > 0 else 99
    vol_valid = [ohlc_code.get(wk_list[j], {}).get('v', 0) for j in range(max(0, idx-9), idx+1)]
    vol_valid = [v for v in vol_valid if v and v > 0]
    avg_vol10 = sum(vol_valid)/len(vol_valid) if vol_valid else 1
    vol_r = w0.get('v', 0)/avg_vol10 if avg_vol10 > 0 else 1
    gain20w = 0
    if idx >= 20:
        prev20_c = ohlc_code.get(wk_list[idx-20], {}).get('c')
        if prev20_c and prev20_c > 0: gain20w = ci/prev20_c - 1
    ma5_list = [ohlc_code.get(wk_list[j], {}).get('c') for j in range(max(0, idx-4), idx+1)]
    ma21_list = [ohlc_code.get(wk_list[j], {}).get('c') for j in range(max(0, idx-20), idx+1)]
    if None in ma5_list or None in ma21_list: return False
    ma5, ma21 = sum(ma5_list)/5, sum(ma21_list)/21
    if ma21 == 0: return False
    return (ci > oi and s2b > 1.0 and l_shadow < body*0.5 and vol_r < 1.5 and ci > ma5 > ma21 and gain20w < 0.5)

def compute_vol_ratio(ohlc_code, wk_list, idx):
    """计算量比 = 本周量 / 10周均量"""
    vol_valid = [ohlc_code.get(wk_list[j], {}).get('v', 0) for j in range(max(0, idx-9), idx+1)]
    vol_valid = [v for v in vol_valid if v and v > 0]
    if not vol_valid: return None
    cur_v = ohlc_code.get(wk_list[idx], {}).get('v', 0)
    avg_v = sum(vol_valid) / len(vol_valid)
    return cur_v / avg_v if avg_v > 0 else None

def run_backtest(vol_threshold, vol_penalty, skip_mode, data_cache):
    """vol_threshold: 量比阈值
       vol_penalty: 超过阈值时扣分（负数）
       skip_mode: True=直接跳过候选, False=扣分"""
    series, all_atr, all_weeks, code_cat, ohlc = data_cache
    if not series: return None
    
    ma_l = 21
    first_avail = {}
    for c, s in series.items():
        first_avail[c] = s[ma_l][0] if len(s) >= ma_l + 1 else None
    
    n_weeks = len(all_weeks) - 1
    if n_weeks < 10: return None
    
    _MIN_YR = 2014
    _si_start = 0
    for i, wk in enumerate(all_weeks):
        if int(wk[:4]) >= _MIN_YR:
            _si_start = max(0, i - 1); break
    _si_end = n_weeks
    
    code_wklist = {c: [wk for wk, _ in s] for c, s in series.items()}
    portfolio = {}; cash = DEF_CAPITAL; eq_curve = []; n_buys = n_sells = 0
    
    for si in range(_si_start, _si_end):
        sig_week, exec_week = all_weeks[si], all_weeks[si+1]
        candidates = []
        for code, s in series.items():
            if first_avail.get(code) and first_avail[code] > sig_week: continue
            idx = None
            for j, (wk, _) in enumerate(s):
                if wk == sig_week: idx = j; break
            if idx is None or idx < 21: continue
            
            price = s[idx][1]
            if price is None or price <= 0: continue
            
            ma5_list = [s[j][1] for j in range(idx-4, idx+1)]
            ma21_list = [s[j][1] for j in range(idx-20, idx+1)]
            if None in ma5_list or None in ma21_list: continue
            ma5, ma21 = sum(ma5_list)/5, sum(ma21_list)/21
            if ma21 == 0: continue
            
            dev = abs(price/ma21 - 1)*100
            if dev > DEF_MAX_DEV: continue
            
            mom = s[idx][1]/s[idx-DEF_LB][1] - 1
            mom1w_v = s[idx][1]/s[idx-1][1] - 1 if idx >= 1 else mom
            mom8w_v = s[idx][1]/s[idx-8][1] - 1 if idx >= 8 else mom
            score = DEF_SC_W1*mom1w_v + DEF_SC_W3*mom + DEF_SC_W8*mom8w_v
            
            ar = all_atr.get(code, {}).get(sig_week)
            if ar is not None and ar < DEF_ATR_F: continue
            
            wk_list = code_wklist.get(code, [])
            c_pat = detect_patterns_v2(ohlc.get(code, {}), wk_list, idx)
            vol_r = compute_vol_ratio(ohlc.get(code, {}), wk_list, idx)
            
            # 高量跳过
            if skip_mode and vol_r is not None and vol_r > vol_threshold:
                continue
            
            candidates.append({'code': code, 'close': price, 'score': score,
                               'dev': dev, 'c_pattern': c_pat, 'vol_r': vol_r})
        
        for c in candidates:
            adj = c['score']
            if c.get('c_pattern'): adj += C_BONUS
            # 量能惩罚（扣分模式）
            if not skip_mode and c.get('vol_r') is not None and c['vol_r'] > vol_threshold:
                adj += vol_penalty
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
                if wk == sig_week: p = cl; break
            if p and p > portfolio[code]['hwm']: portfolio[code]['hwm'] = p
        
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = None
            for wk, cl in series[code]:
                if wk == sig_week: p = cl; break
            if p is None: to_sell.append((code, 'nodata')); continue
            cost_pnl, hwm_pnl = p/pos['buy_price'] - 1, p/pos['hwm'] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, 'stop'))
            elif code not in target_codes:
                to_sell.append((code, 'rebalance'))
        
        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = None
            for wk, cl in series[code]:
                if wk == sig_week: p = cl; break
            cash += pos['weight'] * (p or pos['buy_price'])
            n_sells += 1
        
        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            slot_val = (cash + sum(pos['weight']*pos['buy_price'] for pos in portfolio.values())) / DEF_TOP_N
            for bc in buy_list[:slots]:
                p_exec = None
                for wk, cl in series[bc['code']]:
                    if wk == sig_week: p_exec = cl; break
                if p_exec is None or p_exec <= 0: continue
                weight = slot_val / p_exec
                cost = weight * p_exec
                if cost > cash * 0.98:
                    weight = cash * 0.98 / p_exec
                    cost = weight * p_exec
                if weight <= 0: break
                cash -= cost
                n_buys += 1
                portfolio[bc['code']] = {'weight': weight, 'buy_price': p_exec, 'hwm': p_exec}
        
        equity = cash + sum(pos['weight'] * next((cl for wk, cl in series[c] if wk == exec_week), pos['buy_price']) for c, pos in portfolio.items())
        eq_curve.append({'w': exec_week, 'eq': equity, 'nh': len(portfolio)})
    
    eqs = [e['eq'] for e in eq_curve]
    n = len(eqs)
    if n < 2: return None
    
    init, final = eqs[0], eqs[-1]
    total_ret = (final/init - 1)*100
    years = n/52
    ann_ret = ((final/init)**(1/years) - 1)*100 if years > 0 else 0
    peak = eqs[0]; max_dd = 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq/peak - 1
        if dd < max_dd: max_dd = dd
    
    w_rets = [eqs[i]/eqs[i-1]-1 for i in range(1, n) if eqs[i-1] > 0]
    if w_rets:
        avg_w = statistics.mean(w_rets)
        std_w = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w*52 - 0.02)/(std_w*52**0.5) if std_w > 0 else 0
        win_rate = sum(1 for r in w_rets if r > 0)/len(w_rets)*100
    else:
        sharpe = win_rate = 0
    
    return {'vol_thr': vol_threshold, 'vol_pen': vol_penalty, 'skip': skip_mode,
            'ann_ret': ann_ret, 'total_ret': total_ret, 'max_dd': max_dd*100,
            'sharpe': sharpe, 'win_rate': win_rate, 'n_buys': n_buys, 'n_sells': n_sells}

def main():
    import time
    print("\n" + "="*70)
    print("  HIGH VOLUME PENALTY BACKTEST")
    print("="*70)
    
    print("\n[Data] Loading once...")
    with open(POOL_FILE, encoding='utf-8') as f:
        pool_data = json.load(f)
    etfs = pool_data if isinstance(pool_data, list) else pool_data.get('data', [])
    series, ohlc, all_weeks = load_etf_data(etfs)
    
    # 需要ohlc带OHLCV，重加载一次确保完整
    series2, ohlc2 = {}, {}
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
                    if not recs: break
                    if isinstance(recs[0], list):
                        recs = [{'date': r[0], 'open': r[1], 'high': r[2], 'low': r[3], 'close': r[4], 'vol': r[5]} for r in recs]
                    elif 'w' in recs[0]:
                        recs = [{'date': r.get('date', ''), 'open': r.get('open', r['close']),
                                 'high': r.get('high', r['close']), 'low': r.get('low', r['close']),
                                 'close': r['close'], 'vol': r.get('vol', 0)} for r in recs]
                    weeks = {}
                    for r in recs:
                        ds = r.get('date', '')
                        if not ds: continue
                        try:
                            y, wn, _ = dt.strptime(ds, '%Y-%m-%d').isocalendar()
                            wk = f'{y}-W{wn:02d}'
                            if wk not in weeks or ds > weeks[wk][0]:
                                weeks[wk] = (ds, r['close'], r.get('open', r['close']),
                                             r.get('high', r['close']), r.get('low', r['close']), r.get('vol', 0))
                        except: pass
                    if not weeks: break
                    sorted_wks = sorted(weeks.items())
                    series2[code] = [(wk, cl) for wk, (_, cl, *_) in sorted_wks]
                    ohlc2[code] = {wk: {'c': cl, 'o': op, 'h': hi, 'l': lo, 'v': vo}
                                   for wk, (_, cl, op, hi, lo, vo) in sorted_wks}
                except: pass
    
    all_atr  = compute_atr(ohlc2, all_weeks)
    code_cat = {e['code']: e.get('category', '') or '' for e in etfs}
    print(f"    {len(series2)} ETFs, {len(all_weeks)} weeks")
    data_cache = (series2, all_atr, all_weeks, code_cat, ohlc2)
    
    # 测试配置
    configs = [(0, 0, False)]  # 基线
    for thr in [1.5, 2.0, 2.5, 3.0]:
        for pen in [-0.02, -0.05]:
            configs.append((thr, pen, False))
        configs.append((thr, 0, True))  # 跳过模式
    
    results = []
    for idx, (thr, pen, skip) in enumerate(configs):
        if skip:
            lbl = f"跳过 量比>{thr}"
        elif pen == 0:
            lbl = f"基线"
        else:
            lbl = f"量比>{thr} 罚{pen}"
        print(f"  [{idx+1:02d}/{len(configs)}] {lbl:30s}", end='', flush=True)
        r = run_backtest(thr, pen, skip, data_cache)
        if r:
            dA = r['ann_ret'] - (results[0]['ann_ret'] if results else 0)
            dS = r['sharpe'] - (results[0]['sharpe'] if results else 0)
            print(f" Ann={r['ann_ret']:+.2f}% DD={r['max_dd']:>6.1f}% Sharpe={r['sharpe']:.3f} dA={dA:+.2f} dS={dS:+.3f}")
            results.append(r)
        else:
            print(" FAILED")
    
    baseline = results[0]
    print("\n\n" + "="*95)
    print("  SUMMARY")
    print(f"  Baseline: Ann={baseline['ann_ret']:.2f}% DD={baseline['max_dd']:.1f}% Sharpe={baseline['sharpe']:.3f}")
    print("="*95)
    BL_A = baseline['ann_ret']; BL_S = baseline['sharpe']
    print(f"\n  {'量比>':>6}  {'惩罚':>5}  {'跳过?':>5}  {'Ann.Ret':>8}  {'MaxDD':>7}  {'Sharpe':>7}  {'dAnn':>6}")
    print(f"  {'-'*70}")
    for r in results:
        dA = r['ann_ret']-BL_A; dS = r['sharpe']-BL_S
        mode = '跳过' if r['skip'] else '罚分'
        print(f"  {r['vol_thr']:>6.1f}  {r['vol_pen']:>5.2f}  {mode:>5}  "
              f"{r['ann_ret']:>+8.2f}%  {r['max_dd']:>6.1f}%  {r['sharpe']:>7.3f}  {dA:>+6.2f}")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT_DIR, f'highvol_backtest_{ts}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'baseline': baseline, 'results': results}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out}")

if __name__ == '__main__':
    main()
