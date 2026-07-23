# -*- coding: utf-8 -*-
"""
整合回测框架 v2 — IS/OOS 分离, 逐只ETF注册上市时间
==============================================
IS: 2017-W01 ~ 2022-W52 (6年, ~312周)
OOS: 2023-W01 ~ 2026-W27 (3.5年, ~182周)

测试因子组合:
  - 基线: C+0.02
  - KSFT>0.8+0.02
  - MACD死叉+0.02
  - 跳过量比>1.5
  - 全部组合
"""
import sys, os, json, glob, statistics, time, copy
from datetime import datetime as dt, timedelta
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
C_BONUS     = 0.02
DEF_CAPITAL = 100000.0

def load_all_data():
    """统一加载，返回：etf_list, series, ohlc, avail_weeks, atr_dict"""
    with open(POOL_FILE, encoding='utf-8') as f:
        pool = json.load(f)
    etfs = pool if isinstance(pool, list) else pool.get('data', [])
    
    series, ohlc, code_cat, avail_weeks = {}, {}, {}, set()
    
    for etf in etfs:
        code, cat = etf['code'], etf.get('category', '') or ''
        code_cat[code] = cat
        # 查找文件
        matches = glob.glob(os.path.join(HISTORY_DIR, f'{code}.json'))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}.json'))
        if not matches:
            continue
        try:
            with open(matches[0], encoding='utf-8') as f:
                raw = f.read().replace('NaN', 'null')
            d = json.loads(raw)
            recs = d.get('records', []) if isinstance(d, dict) else d
            if not recs:
                continue
            if isinstance(recs[0], list):
                recs = [{'date': r[0], 'open': r[1], 'high': r[2], 'low': r[3], 'close': r[4], 'vol': r[5]} for r in recs]
            elif 'w' in recs[0]:
                recs = [{'date': r.get('date', ''), 'open': r.get('open', r['close']),
                         'high': r.get('high', r['close']), 'low': r.get('low', r['close']),
                         'close': r['close'], 'vol': r.get('vol', 0)} for r in recs]
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
                                     r.get('high', r['close']), r.get('low', r['close']), r.get('vol', 0))
                except:
                    pass
            if not weeks:
                continue
            srt = sorted(weeks.items())
            series[code] = [(wk, v[1]) for wk, v in srt]
            ohlc[code] = {wk: {'o': v[2], 'h': v[3], 'l': v[4], 'c': v[1], 'v': v[5]} for wk, v in srt}
            avail_weeks.update(w for w, _ in srt)
        except:
            continue
    
    all_weeks = sorted(avail_weeks)
    
    # ATR
    atr = {}
    for code, wd in ohlc.items():
        if len(wd) < 30:
            continue
        wk_list = sorted(wd.keys())
        trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur, prv = wd[wk_list[i]], wd[wk_list[i-1]]
            h, l, pc = cur['h'], cur['l'], prv['c']
            trs[i] = max(h - l, abs(h - pc), abs(l - pc))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:]) / 14
                slow = sum(vals) / 21
                if slow > 0:
                    atrs[wk_list[i]] = fast / slow
        atr[code] = atrs
    
    return etfs, series, ohlc, code_cat, all_weeks, atr

def compute_ema(data, n):
    if not data:
        return None
    k = 2.0 / (n + 1)
    e = data[0]
    for v in data[1:]:
        e = v * k + e * (1 - k)
    return e

def calc_factors(code, wk_list, idx, series, ohlc, atr):
    """一次性计算所有因子，返回dict"""
    ohlc_c = ohlc.get(code, {})
    srt = series.get(code, [])
    
    result = {'vol_ratio': None, 'ksft': None, 'macd_cross': 0, 'c_pat': False}
    
    # --- 基础数据检查 ---
    if idx < 21 or idx >= len(srt):
        return result
    price = srt[idx][1]
    if price is None or price <= 0:
        return result
    
    # MA5/MA21
    ma5 = sum(srt[j][1] for j in range(idx-4, idx+1)) / 5
    ma21 = sum(srt[j][1] for j in range(idx-20, idx+1)) / 21
    if ma21 == 0:
        return result
    
    dev = abs(price / ma21 - 1) * 100
    if dev > DEF_MAX_DEV:
        return result
    
    # ATR过滤
    sig_week = srt[idx][0]
    ar = atr.get(code, {}).get(sig_week)
    if ar is not None and ar < DEF_ATR_F:
        return result
    
    # --- 动量评分 ---
    mom = price / srt[idx-DEF_LB][1] - 1
    mom1w = price / srt[idx-1][1] - 1 if idx >= 1 else mom
    mom8w = price / srt[idx-8][1] - 1 if idx >= 8 else mom
    score = DEF_SC_W1 * mom1w + DEF_SC_W3 * mom + DEF_SC_W8 * mom8w
    result['score'] = score
    result['dev'] = dev
    
    # --- 仙人指路(C型) ---
    w0 = ohlc_c.get(sig_week, {})
    if w0 and None not in [w0.get('c'), w0.get('o'), w0.get('h'), w0.get('l')]:
        ci, oi, hi, li = w0['c'], w0['o'], w0['h'], w0['l']
        body = abs(ci - oi)
        u_shadow = hi - max(ci, oi)
        l_shadow = min(ci, oi) - li
        s2b = u_shadow / body if body > 0 else 99
        vol_vals = [ohlc_c.get(wk_list[j], {}).get('v', 0) for j in range(max(0, idx-9), idx+1)]
        vol_vals = [v for v in vol_vals if v and v > 0]
        avg_v10 = sum(vol_vals) / len(vol_vals) if vol_vals else 1
        vol_r = w0.get('v', 0) / avg_v10 if avg_v10 > 0 else 1
        g20 = 0
        if idx >= 20:
            pc = ohlc_c.get(wk_list[idx-20], {}).get('c')
            if pc and pc > 0:
                g20 = ci / pc - 1
        result['c_pat'] = (ci > oi and s2b > 1.0 and l_shadow < body * 0.5
                           and vol_r < 1.5 and ci > ma5 > ma21 and g20 < 0.5)
        result['vol_ratio'] = vol_r
        
        # --- KSFT ---
        if hi != li:
            result['ksft'] = (ci - li) / (hi - li)
        
        # --- MACD ---
        if idx >= 34 and None not in [ci, oi]:
            all_prices = [srt[j][1] for j in range(idx+1)]
            if len(all_prices) >= 34:
                e12 = compute_ema(all_prices[-12:], 12) if len(all_prices) >= 12 else None
                e26 = compute_ema(all_prices[-26:], 26) if len(all_prices) >= 26 else None
                if e12 is not None and e26 is not None:
                    dif = e12 - e26
                    dif_hist = []
                    for i in range(26, len(all_prices)):
                        w12 = all_prices[max(0, i-11):i+1]
                        w26 = all_prices[max(0, i-25):i+1]
                        if len(w12) >= 12 and len(w26) >= 26:
                            e12_i = compute_ema(w12, 12)
                            e26_i = compute_ema(w26, 26)
                            if e12_i is not None and e26_i is not None:
                                dif_hist.append(e12_i - e26_i)
                    if len(dif_hist) >= 2:
                        signal = compute_ema(dif_hist[-9:], 9) if len(dif_hist) >= 9 else dif_hist[-1]
                        result['macd_cross'] = 1 if dif > signal else -1
    
    return result

def run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
            is_end_idx, oos_end_idx,
            enable_c=True, enable_ksft=False, enable_macd=False, enable_skip_vol=False,
            c_bonus=0.02, ksft_bonus=0.02, ksft_thr=0.8,
            macd_bonus=0.02, macd_mode=-1,
            vol_thr=1.5):
    """在[IS或OOS]区间内运行一次完整回测"""
    
    code_wklist = {c: [wk for wk, _ in s] for c, s in series.items()}
    
    # 计算每只ETF在区间起始时可用的最小idx
    first_idx = {}
    for code, s in series.items():
        for j, (wk, _) in enumerate(s):
            if wk == all_weeks[is_end_idx]:
                first_idx[code] = j
                break
    
    portfolio = {}
    cash = DEF_CAPITAL
    eq_curve = []
    n_buys = n_sells = 0
    year_rets = defaultdict(list)
    
    for si in range(is_end_idx, oos_end_idx):
        sig_week = all_weeks[si]
        exec_week = all_weeks[si + 1]
        
        candidates = []
        for code, s in series.items():
            fi = first_idx.get(code)
            if fi is None:
                continue
            idx = fi + (si - is_end_idx)
            if idx < 21 or idx >= len(s):
                continue
            
            f = calc_factors(code, code_wklist.get(code, []), idx, series, ohlc, atr)
            if 'score' not in f:
                continue
            
            # 应用过滤
            if enable_skip_vol and f.get('vol_ratio') is not None and f['vol_ratio'] > vol_thr:
                continue
            
            adj = f['score']
            if enable_c and f.get('c_pat'):
                adj += c_bonus
            if enable_ksft and f.get('ksft') is not None and f['ksft'] >= ksft_thr:
                adj += ksft_bonus
            if enable_macd and f.get('macd_cross') == macd_mode:
                adj += macd_bonus
            
            candidates.append({'code': code, 'close': s[idx][1], '_adj': adj,
                               'cat': code_cat.get(code, '')})
        
        candidates.sort(key=lambda x: x['_adj'], reverse=True)
        
        # 同类只选最强
        cats = set()
        target = []
        for c in candidates:
            if c['cat'] not in cats:
                cats.add(c['cat'])
                target.append(c)
        target = target[:DEF_TOP_N]
        target_codes = {t['code'] for t in target}
        
        # 更新HWM
        for code in portfolio:
            p = None
            for wk, cl in series[code]:
                if wk == sig_week:
                    p = cl
                    break
            if p and p > portfolio[code]['hwm']:
                portfolio[code]['hwm'] = p
        
        # 卖出
        to_sell = []
        for code, pos in portfolio.items():
            p = None
            for wk, cl in series[code]:
                if wk == sig_week:
                    p = cl
                    break
            if p is None:
                to_sell.append((code, 'nodata'))
                continue
            cost_pnl = p / pos['buy_price'] - 1
            hwm_pnl = p / pos['hwm'] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, 'stop'))
            elif code not in target_codes:
                to_sell.append((code, 'rebalance'))
        
        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = None
            for wk, cl in series[code]:
                if wk == sig_week:
                    p = cl
                    break
            cash += pos['weight'] * (p or pos['buy_price'])
            n_sells += 1
        
        # 买入
        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t['code'] not in portfolio]
            total_assets = cash + sum(pos['weight'] * pos['buy_price'] for pos in portfolio.values())
            slot_val = total_assets / DEF_TOP_N
            for bc in buy_list[:slots]:
                p_exec = None
                for wk, cl in series[bc['code']]:
                    if wk == sig_week:
                        p_exec = cl
                        break
                if p_exec is None or p_exec <= 0:
                    continue
                weight = slot_val / p_exec
                cost = weight * p_exec
                if cost > cash * 0.98:
                    weight = cash * 0.98 / p_exec
                    cost = weight * p_exec
                if weight <= 0:
                    break
                cash -= cost
                portfolio[bc['code']] = {'weight': weight, 'buy_price': p_exec, 'hwm': p_exec}
                n_buys += 1
        
        # 权益曲线
        equity = cash + sum(
            pos['weight'] * (next((cl for wk, cl in series[c] if wk == exec_week), pos['buy_price']))
            for c, pos in portfolio.items()
        )
        eq_curve.append({'w': exec_week, 'eq': equity, 'nh': len(portfolio)})
        yr = exec_week[:4]
        year_rets[yr].append(equity)
    
    return compute_stats(eq_curve, n_buys, n_sells)

def compute_stats(eq_curve, n_buys, n_sells):
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
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52 ** 0.5) if std_w > 0 else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = win_rate = 0
    
    # 逐年
    yr_data = defaultdict(list)
    for e in eq_curve:
        yr_data[e['w'][:4]].append(e['eq'])
    yearly = {}
    for yr in sorted(yr_data):
        es = yr_data[yr]
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
        'ann_ret': ann_ret, 'total_ret': total_ret,
        'max_dd': max_dd * 100, 'sharpe': sharpe,
        'win_rate': win_rate, 'n_buys': n_buys, 'n_sells': n_sells,
        'n_weeks': n, 'yearly': yearly,
    }

def main():
    print("\n" + "="*70)
    print("  INTEGRATED BACKTEST v2 — IS/OOS")
    print("="*70)
    
    t0 = time.time()
    print("\n[Data] Loading...")
    etfs, series, ohlc, code_cat, all_weeks, atr = load_all_data()
    print(f"    {len(series)} ETFs, {len(all_weeks)} weeks ({all_weeks[0]} ~ {all_weeks[-1]})")
    
    # 定位IS/OOS边界
    is_start = 0
    is_end = 0
    oos_end = len(all_weeks) - 1
    
    for i, wk in enumerate(all_weeks):
        if wk == '2017-W01':
            is_start = max(0, i - 1)
        if wk == '2023-W01':
            is_end = i
    
    print(f"\n  IS: {all_weeks[is_start]} ~ {all_weeks[is_end-1]} ({(is_end-is_start)} wks)")
    print(f"  OOS: {all_weeks[is_end]} ~ {all_weeks[oos_end-1]} ({(oos_end-is_end)} wks)")
    
    # --- 测试所有因子组合 ---
    configs = [
        # (label, enable_c, enable_ksft, enable_macd, enable_skip_vol)
        ('Baseline (C+0.02)',     True,  False, False, False),
        ('+KSFT>0.8+0.02',        True,  True,  False, False),
        ('+MACD死叉+0.02',        True,  False, True,  False),
        ('+跳过 量比>1.5',        True,  False, False, True),
        ('+KSFT+MACD',            True,  True,  True,  False),
        ('+KSFT+跳过',            True,  True,  False, True),
        ('+MACD+跳过',            True,  False, True,  True),
        ('ALL (全部)',            True,  True,  True,  True),
    ]
    
    print(f"\n{'#'*80}")
    print(f"  # IS (2017~2022) — 因子筛选")
    print(f"{'#'*80}")
    
    is_results = []
    for label, ec, ek, em, es in configs:
        print(f"  {label:25s}", end='', flush=True)
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                    is_start, is_end, ec, ek, em, es,
                    c_bonus=0.02, ksft_bonus=0.02, ksft_thr=0.8,
                    macd_bonus=0.02, macd_mode=-1, vol_thr=1.5)
        if r:
            is_results.append((label, ec, ek, em, es, r))
            dA = r['ann_ret'] - (is_results[0][5]['ann_ret'] if len(is_results) > 1 else r['ann_ret'])
            tag = '★ BEST' if len(is_results) > 1 and r['sharpe'] == max(x[5]['sharpe'] for x in is_results) else ''
            print(f"  Ann={r['ann_ret']:+7.2f}%  DD={r['max_dd']:>6.1f}%  Sharpe={r['sharpe']:.3f}  {tag}")
    
    # 选IS最优（按夏普）
    best_idx = max(range(len(is_results)), key=lambda i: is_results[i][5]['sharpe'])
    best_label, best_ec, best_ek, best_em, best_es, best_is_r = is_results[best_idx]
    baseline_is_r = is_results[0][5]
    
    print(f"\n  IS最优: {best_label}")
    print(f"  IS基线: {is_results[0][0]}")
    
    # --- OOS验证 ---
    print(f"\n{'#'*80}")
    print(f"  # OOS (2023~2026) — 最优配置验证")
    print(f"{'#'*80}")
    
    # 跑全部配置在OOS上
    oos_results = []
    for label, ec, ek, em, es in configs:
        print(f"  {label:25s}", end='', flush=True)
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                    is_end, oos_end, ec, ek, em, es,
                    c_bonus=0.02, ksft_bonus=0.02, ksft_thr=0.8,
                    macd_bonus=0.02, macd_mode=-1, vol_thr=1.5)
        if r:
            dA = r['ann_ret'] - oos_results[0][1]['ann_ret'] if oos_results else 0
            oos_results.append((label, r))
            print(f"  Ann={r['ann_ret']:+7.2f}%  DD={r['max_dd']:>6.1f}%  Sharpe={r['sharpe']:.3f}")
    
    # --- 汇总表 ---
    print(f"\n{'='*100}")
    print(f"  {'配置':25s}  {'IS年化':>8}  {'IS夏普':>8}  {'IS-DD':>7}  {'OOS年化':>8}  {'OOS夏普':>8}  {'OOS-DD':>7}  {'差值':>6}")
    print(f"  {'-'*100}")
    
    for i, (label, ec, ek, em, es, is_r) in enumerate(is_results):
        oos_r = oos_results[i][1]
        diff = oos_r['ann_ret'] - is_r['ann_ret']
        star = ' ★' if label == best_label else ''
        print(f"  {label:25s}  {is_r['ann_ret']:>+8.2f}%  {is_r['sharpe']:>8.3f}  {is_r['max_dd']:>6.1f}%  "
              f"{oos_r['ann_ret']:>+8.2f}%  {oos_r['sharpe']:>8.3f}  {oos_r['max_dd']:>6.1f}%  {diff:>+6.2f}%{star}")
    
    # --- 结论 ---
    print(f"\n{'#'*80}")
    print(f"  # 结论")
    print(f"{'#'*80}")
    print(f"  IS最优(夏普): {best_label}")
    best_oos_r = oos_results[best_idx][1]
    print(f"  IS: Ann={best_is_r['ann_ret']:+.2f}% Sharpe={best_is_r['sharpe']:.3f} DD={best_is_r['max_dd']:.1f}%")
    print(f"  OOS: Ann={best_oos_r['ann_ret']:+.2f}% Sharpe={best_oos_r['sharpe']:.3f} DD={best_oos_r['max_dd']:.1f}%")
    
    # 逐年对比
    print(f"\n  # 逐年收益 (IS最优 vs 基线)")
    print(f"  {'年':>6}  {'IS最优-OOS':>12}  {'基线-OOS':>12}")
    for yr in sorted(set(list(best_oos_r.get('yearly', {}).keys()) + list(oos_results[0][1].get('yearly', {}).keys()))):
        bv = best_oos_r.get('yearly', {}).get(yr, {}).get('ret', 0)
        bv2 = oos_results[0][1].get('yearly', {}).get(yr, {}).get('ret', 0)
        print(f"  {yr:>6}  {bv:>+11.2f}%  {bv2:>+11.2f}%")
    
    # 同时跑逐年IS最优的IS期
    print(f"\n  # 逐年收益 (IS最优-IS期)")
    print(f"  {'年':>6}  {'收益':>8}")
    for yr in sorted(best_is_r.get('yearly', {}).keys()):
        v = best_is_r['yearly'][yr]['ret']
        print(f"  {yr:>6}  {v:>+8.2f}%")
    
    # 保存
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT_DIR, f'integrated_v2_{ts}.json')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = {
        'is_period': (all_weeks[is_start], all_weeks[is_end-1]),
        'oos_period': (all_weeks[is_end], all_weeks[oos_end-1]),
        'baseline_is': baseline_is_r,
        'best_config': best_label,
        'best_is': best_is_r,
        'best_oos': best_oos_r,
        'all_is': [(l, r) for l, *_, r in is_results],
        'all_oos': oos_results,
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved: {out}")
    print(f"Time: {time.time()-t0:.0f}s")

if __name__ == '__main__':
    main()
