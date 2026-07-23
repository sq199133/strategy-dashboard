#!/usr/bin/env python3


"""v4.8 weekly momentum scan  |  MA21 hard filter  dev=30%  no c_bonus  skip vr>1.5"""
# -*- coding: utf-8 -*-



"""v4.7 weekly momentum scan  |  MA21纭繃婊? 鏃燾_bonus  璺宠繃閲忔瘮>1.5"""







import json, os, sys, time, urllib.request



from datetime import datetime, timedelta



from collections import defaultdict







if sys.platform == 'win32':



    sys.stdout.reconfigure(encoding='utf-8', errors='replace')



    sys.stderr.reconfigure(encoding='utf-8', errors='replace')







POOL_FILE = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'



HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'


OUTPUT_DIR = r'D:\Qclaw_Trading\scan_results'



DEFAULT_MAX_DEV = 30



DEFAULT_TOP_N = 1



DEFAULT_LB = 3



MA_S = 5



MA_L = 21



KLINE_DAYS = 300



ATR_RATIO = 0.85



# ---- v4.6.1 褰㈡€佸姞鍒嗗父閲?----
# C锛堜粰浜烘寚璺級: 浣庝綅/涓+闃崇嚎+闀夸笂褰?涓嬪奖鐭?娓╁拰閲?鍧囩嚎澶氬ご
# B1锛堢孩涓夊叺锛? 杩炵画3鍛ㄩ槼绾匡紝浣庣偣鎶珮锛岄噺鑳界ǔ瀹氾紙鍥炴祴鏄剧ず璐熸晥鏋滐紝宸茬鐢級
# ---- v4.7 MA21纭繃婊?+ c_bonus鍙厤缃?----
C_BONUS  = 0.00   # 浠欎汉鎸囪矾鍔犲垎锛坴4.7: 宸茬Щ闄わ紝MA21纭繃婊ゆ洿鏈夋晥锛?
B1_BONUS = 0.00   # 绾笁鍏靛姞鍒嗗凡绉婚櫎
VOL_RATIO_THRESH = 1.5  # 閲忔瘮闃堝€硷細瓒呰繃鍒欒烦杩囷紙楂橀噺鑳藉嚭璐т俊鍙凤級v4.6.2



SCORE_W1 = 0.5



SCORE_W3 = 0.5







def load_pool():



    with open(POOL_FILE, 'r', encoding='utf-8') as f:



        data = json.load(f)



    etfs = data.get('data', data.get('etfs', []))



    print(f"Pool: {len(etfs)} ETFs")



    return etfs







def get_prefix(code):



    return 'sh' if code.startswith('6') else 'sz'







def fetch_kline(code):



    prefix = get_prefix(code)



    for alt in [prefix, 'sz' if prefix == 'sh' else 'sh']:



        sym = f'{alt}{code}'



        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,{KLINE_DAYS},qfq'



        try:



            req = urllib.request.Request(url, headers={



                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'



            })



            with urllib.request.urlopen(req, timeout=12) as resp:



                raw = json.loads(resp.read().decode('utf-8'))



            d = raw.get('data', {}).get(sym, {})



            klines = d.get('qfqday', []) or d.get('day', [])



            if klines:



                return [(k[0], float(k[1]), float(k[2]),



                         float(k[3]), float(k[4]), int(float(k[5]))) for k in klines]



            if d:



                return []



        except Exception:



            time.sleep(0.5)



        if alt != prefix:



            break



    return []







def load_weekly_file(code):


    """Load weekly data from local history_long_v2/ directory"""


    fp = os.path.join(HISTORY_DIR, f'{code}.json')


    try:


        with open(fp, 'r', encoding='utf-8') as f:


            data = json.load(f)


    except (FileNotFoundError, json.JSONDecodeError):


        return None


    records = data.get('records', [])


    if not records:


        return None


    # Compute aggregate fields from records (already weekly)


    wk = []


    for r in records:


        wk.append({


            'week': r['w'],


            'date_end': r['date'],


            'close': r['close'],


            'open': r['open'],


            'high': r['high'],


            'low': r['low'],


            'vol': r['vol'],


        })


    return wk








def agg_weekly(daily):



    weeks = defaultdict(lambda: {'d': [], 'o': [], 'h': [], 'l': [], 'c': [], 'v': []})



    for ds, o, c, h, l, v in daily:



        try:



            dt = datetime.strptime(ds, '%Y-%m-%d')



        except ValueError:



            continue



        y, w, _ = dt.isocalendar()



        k = f'{y}-W{w:02d}'



        ww = weeks[k]



        ww['d'].append(ds); ww['o'].append(o); ww['h'].append(h)



        ww['l'].append(l); ww['c'].append(c); ww['v'].append(v)



    return [{'week': k, 'date_end': w['d'][-1], 'close': w['c'][-1],



             'open': w['o'][0], 'high': max(w['h']), 'low': min(w['l']),



             'vol': sum(w['v'])}



            for k, w in sorted(weeks.items())]







def filter_completed_weeks(wk):



    """filter to completed weeks only"""



    today = datetime.now()



    days_to_fri = (today.weekday() - 4) % 7



    if days_to_fri == 0:



        days_to_fri = 7



    cutoff = (today - timedelta(days=days_to_fri)).strftime('%Y-%m-%d')



    filtered = [w for w in wk if w['date_end'] <= cutoff]



    if not filtered:



        return wk



    skipped = len(wk) - len(filtered)



    if skipped > 0:



        print(f'Filtered {skipped} partial week(s)')



    return filtered







#!/usr/bin/env python3



# -*- coding: utf-8 -*-



"""v5.1 weekly momentum scan"""







import json, os, sys, time, urllib.request



from datetime import datetime, timedelta



from collections import defaultdict







if sys.platform == 'win32':



    sys.stdout.reconfigure(encoding='utf-8', errors='replace')



    sys.stderr.reconfigure(encoding='utf-8', errors='replace')







POOL_FILE = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'



HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'


OUTPUT_DIR = r'D:\Qclaw_Trading\scan_results'



DEFAULT_MAX_DEV = 30



DEFAULT_TOP_N = 1



DEFAULT_LB = 3



MA_S = 5



MA_L = 21



KLINE_DAYS = 300



ATR_RATIO = 0.85







SCORE_W1 = 0.5



SCORE_W3 = 0.5







def load_pool():



    with open(POOL_FILE, 'r', encoding='utf-8') as f:



        data = json.load(f)



    etfs = data.get('data', data.get('etfs', []))



    print(f"Pool: {len(etfs)} ETFs")



    return etfs







def get_prefix(code):



    return 'sh' if code.startswith('6') else 'sz'







def fetch_kline(code):



    prefix = get_prefix(code)



    for alt in [prefix, 'sz' if prefix == 'sh' else 'sh']:



        sym = f'{alt}{code}'



        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,{KLINE_DAYS},qfq'



        try:



            req = urllib.request.Request(url, headers={



                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'



            })



            with urllib.request.urlopen(req, timeout=12) as resp:



                raw = json.loads(resp.read().decode('utf-8'))



            d = raw.get('data', {}).get(sym, {})



            klines = d.get('qfqday', []) or d.get('day', [])



            if klines:



                return [(k[0], float(k[1]), float(k[2]),



                         float(k[3]), float(k[4]), int(float(k[5]))) for k in klines]



            if d:



                return []



        except Exception:



            time.sleep(0.5)



        if alt != prefix:



            break



    return []







def load_weekly_file(code):


    """Load weekly data from local history_long_v2/ directory"""


    fp = os.path.join(HISTORY_DIR, f'{code}.json')


    try:


        with open(fp, 'r', encoding='utf-8') as f:


            data = json.load(f)


    except (FileNotFoundError, json.JSONDecodeError):


        return None


    records = data.get('records', [])


    if not records:


        return None


    # Compute aggregate fields from records (already weekly)


    wk = []


    for r in records:


        wk.append({


            'week': r['w'],


            'date_end': r['date'],


            'close': r['close'],


            'open': r['open'],


            'high': r['high'],


            'low': r['low'],


            'vol': r['vol'],


        })


    return wk








def agg_weekly(daily):



    weeks = defaultdict(lambda: {'d': [], 'o': [], 'h': [], 'l': [], 'c': [], 'v': []})



    for ds, o, c, h, l, v in daily:



        try:



            dt = datetime.strptime(ds, '%Y-%m-%d')



        except ValueError:



            continue



        y, w, _ = dt.isocalendar()



        k = f'{y}-W{w:02d}'



        ww = weeks[k]



        ww['d'].append(ds); ww['o'].append(o); ww['h'].append(h)



        ww['l'].append(l); ww['c'].append(c); ww['v'].append(v)



    return [{'week': k, 'date_end': w['d'][-1], 'close': w['c'][-1],



             'open': w['o'][0], 'high': max(w['h']), 'low': min(w['l']),



             'vol': sum(w['v'])}



            for k, w in sorted(weeks.items())]







def filter_completed_weeks(wk):



    """filter to completed weeks only"""



    today = datetime.now()



    days_to_fri = (today.weekday() - 4) % 7



    if days_to_fri == 0:



        days_to_fri = 7



    cutoff = (today - timedelta(days=days_to_fri)).strftime('%Y-%m-%d')



    filtered = [w for w in wk if w['date_end'] <= cutoff]



    if not filtered:



        return wk



    skipped = len(wk) - len(filtered)



    if skipped > 0:



        print(f'Filtered {skipped} partial week(s)')



    return filtered







def calc(wk):



    n = len(wk)



    cl = [w['close'] for w in wk]



    hi = [w['high'] for w in wk]



    lo = [w['low'] for w in wk]



    vo = [w['vol'] for w in wk]  # v4.6: volumes for pattern detection
    if n < MA_L + 1:



        return None



    # Precompute ATR ratio for each week from i>=21



    atr_ratios = {}



    for i in range(21, n):



        # TR: max(high-low, |high-prev_close|, |low-prev_close|)



        trs = []



        for j in range(i-20, i+1):



            h, l = hi[j], lo[j]



            pc = cl[j-1]



            tr = max(h - l, abs(h - pc), abs(l - pc))



            trs.append(tr)



        fast = sum(trs[-14:]) / 14



        slow = sum(trs) / 21



        if slow > 0:



            atr_ratios[wk[i]['week']] = fast / slow



    out = []



    for i in range(MA_L, n):



        ma5 = sum(cl[i-MA_S+1:i+1]) / MA_S



        ma21 = sum(cl[i-MA_L+1:i+1]) / MA_L



        mom = (cl[i] / cl[i-DEFAULT_LB] - 1) if i >= DEFAULT_LB else None



        dev = cl[i] / ma21 - 1 if ma21 > 0 else None



        # v4.5: composite momentum score


        mom1w = cl[i] / cl[i-1] - 1 if i >= 1 else None



        mom8w = cl[i] / cl[i-7] - 1 if i >= 7 else None



        if mom1w is not None and mom8w is not None and mom is not None:



            score = SCORE_W1 * mom1w + SCORE_W3 * mom + (1 - SCORE_W1 - SCORE_W3) * mom8w



        else:



            score = mom



        atr_r = atr_ratios.get(wk[i]['week'], None) if ATR_RATIO else None




        # ---- v4.6 褰㈡€佽瘑鍒?(C浠欎汉鎸囪矾 + B1绾笁鍏? ----
        body      = abs(cl[i] - wk[i]['open'])
        u_shadow  = hi[i] - max(cl[i], wk[i]['open'])
        l_shadow  = min(cl[i], wk[i]['open']) - lo[i]
        s2b       = u_shadow / body if body > 0 else 99
        avg_vol10 = sum(vo[i-9:i+1]) / 10
        vol_r     = vo[i] / avg_vol10 if avg_vol10 > 0 else 1
        vol_ratio = vol_r  # v4.6.2
        gain20w   = cl[i] / cl[i-20] - 1 if i >= 20 else 0
        c_pattern = (
            cl[i] > wk[i]['open']           # 闃崇嚎
            and s2b > 1.0                    # 涓婂奖>瀹炰綋
            and l_shadow < body * 0.5       # 涓嬪奖<瀹炰綋涓€鍗?
            and vol_r < 1.5                  # 娓╁拰鏀鹃噺
            and cl[i] > ma5 > ma21          # 鍧囩嚎澶氬ご
            and gain20w < 0.5               # 浣庝綅/涓
        )
        b1_ok = False
        if i >= 2:
            w1, w2, w3 = wk[i-2], wk[i-1], wk[i]
            w1_b = w1['close'] > w1['open']
            w2_b = w2['close'] > w2['open']
            w3_b = cl[i] > wk[i]['open']
            w1_up = w2['low'] > w1['low'] * 0.98
            vol_ok = all(vo[j] < avg_vol10 * 1.5 for j in range(i-2, i+1))
            b1_ok = w1_b and w2_b and w3_b and w1_up and vol_ok
        out.append({'week': wk[i]['week'], 'date_end': wk[i]['date_end'],



                     'close': cl[i], 'ma5': ma5, 'ma21': ma21,



                     'mom': mom, 'mom1w': mom1w, 'mom8w': mom8w,



                     'score': score, 'dev': dev, 'atr_ratio': atr_r,
                     'c_pattern': c_pattern, 'b1_pattern': b1_ok, 'vol_ratio': vol_ratio})



    return out











def check(ind, md):



    if not ind: return False, {}



    m = ind.get('score', ind['mom'])



    p, a5, a21, d = ind['close'], ind['ma5'], ind['ma21'], ind['dev']



    c1 = m is not None and m > 0



    c2 = p > a21   # v4.7: MA21纭繃婊わ紙涓嶈姹俶a5>ma21锛屽彧瑕佹眰浠锋牸绔欎笂MA21锛?



    c3 = d is not None and d <= md / 100.0



    c4 = True



    if ATR_RATIO is not None:



        ar = ind.get('atr_ratio')



        c4 = ar is None or ar >= ATR_RATIO



    return c1 and c2 and c3 and c4, {'c1': c1, 'c2': c2, 'c3': c3, 'c4': c4}











def main():



    import argparse



    ap = argparse.ArgumentParser()



    ap.add_argument('--max-dev', type=float, default=DEFAULT_MAX_DEV)



    ap.add_argument('--top-n', type=int, default=DEFAULT_TOP_N)



    ap.add_argument('--holdings', type=str, default='')



    a = ap.parse_args()







    print(f"{'='*60}")



    print(f"  v4.5 Weekly Momentum Scan (Composite Score + ATR Filter)")



    print(f"  MA{MA_S}/{MA_L}, LB={DEFAULT_LB}, dev<={a.max_dev}%, top={a.top_n}")



    print(f"  Score: composite w1={SCORE_W1} w3={SCORE_W3} w8={1-SCORE_W1-SCORE_W3:.1f}")




    print(f"  ATR filter: {ATR_RATIO:.2f} (ATR14/ATR21 < {ATR_RATIO:.2f} -> skip)")

    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")



    print(f"{'='*60}\n")







    etfs = load_pool()



    hs = set(a.holdings.split(',')) if a.holdings else set()



    results, failed = [], 0







    for idx, etf in enumerate(etfs):



        code = etf['code']



        name = etf.get('name', code)



        pct = (idx + 1) / len(etfs) * 100



        sys.stdout.write(f'\r[{idx+1}/{len(etfs)}] {pct:.0f}% {code}     ')



        sys.stdout.flush()







        kl = fetch_kline(code)



        if not kl or len(kl) < 30:



            failed += 1



            continue



        wk = agg_weekly(kl)



        wk = filter_completed_weeks(wk)



        if len(wk) < MA_L + 1:



            failed += 1



            continue



        ind = calc(wk)



        if not ind:



            failed += 1



            continue



        last = ind[-1]



        ok, cc = check(last, a.max_dev)



        



        results.append({



            'code': code, 'name': name, 'cat': etf.get('category', ''),



            'close': last['close'], 'ma5': last['ma5'], 'ma21': last['ma21'],



            'mom': last['mom'], 'mom1w': last.get('mom1w'), 'mom8w': last.get('mom8w'),



            'score': last.get('score', last['mom']), 'dev': last['dev'],



            'date_end': last['date_end'], 'passed': ok,



            'c1': cc.get('c1'), 'c2': cc.get('c2'), 'c3': cc.get('c3'), 'c4': cc.get('c4', True),



            'c_pattern': last.get('c_pattern'), 'b1_pattern': last.get('b1_pattern'), 'vol_ratio': last.get('vol_ratio'),



            'holding': code in hs, 'n_weeks': len(wk),



        })



        if (idx + 1) % 15 == 0:



            time.sleep(1)







    print(f'\rDone. OK={len(results)} FAIL={failed}                     ')







    # === Build target portfolio ===



    # v4.6.2: 杩囨护楂橀噺鑳紼TF锛堥噺姣?1.5涓哄嚭璐т俊鍙凤級
    skip_high_vol = 0
    for r in results:
        vr = r.get('vol_ratio')
        if vr is not None and vr > VOL_RATIO_THRESH:
            r['passed'] = False
            r['skip_reason'] = f'vol_ratio={vr:.2f}>1.5'
            skip_high_vol += 1
    if skip_high_vol > 0:
        print(f'  Skipped {skip_high_vol} high-volume ETFs (vol_ratio>1.5)')
    # v4.6: apply pattern bonus before sorting
    for r in results:
        if r['passed']:
            adj = r.get('score', r['mom'])
            if r.get('c_pattern'):  adj += C_BONUS   # +0.02浠欎汉鎸囪矾
            if r.get('b1_pattern'): adj += B1_BONUS  # +0.00绾笁鍏?
            r['_adj_score'] = adj
    qual = sorted([r for r in results if r['passed']],
                  key=lambda x: x.get('_adj_score', x.get('score', x['mom'])), reverse=True)








    # Category dedup removed 2026-07-05 (verified harmful in OOS)
    target = qual[:a.top_n]







    # === Trade actions ===



    target_codes = {r['code'] for r in target}







    if hs:



        sell = [r for r in results if r['holding'] and r['code'] not in target_codes]



        buy = [r for r in target if not r['holding']]



        keep = [r for r in target if r['holding']]



    else:



        sell = []



        buy = target



        keep = []







    # === Output ===



    print(f"\n{'='*60}")



    print(f"  SCAN SUMMARY")



    print(f"{'='*60}")



    print(f"  Total: {len(etfs)} | OK: {len(results)} | Fail: {failed}")



    print(f"  Qualified: {len(qual)}")



    print(f"{'='*60}\n")







    # -- Target Portfolio --



    print(f"TARGET PORTFOLIO (Top {a.top_n}, equal weight):\n")



    print(f"{'#':>2} {'code':<8} {'name':<16} {'cat':<12} {'close':>7} "



          f"{'MA5':>7} {'MA21':>7} {'score%':>7} {'mom%':>7} {'dev%':>7} {'ATR':>5} {'action'}")



    print('-' * 100)



    for i, r in enumerate(target):



        if r['holding']:



            action = 'HOLD'



        else:



            action = 'BUY'



        print(f"{i+1:>2} {r['code']:<8} {r['name']:<16} {r['cat']:<12} "



              f"{r['close']:>7.3f} {r['ma5']:>7.3f} {r['ma21']:>7.3f} "



              f"{r['score']*100:>+6.1f}% {r['mom']*100:>+6.1f}% {r['dev']*100:>6.1f}% {r.get('atr_ratio',1)*100:>4.0f}%  {action}")







    # -- Trade actions --



    print(f"\n{'='*60}")



    print(f"  TRADE ACTIONS")



    print(f"{'='*60}\n")







    if sell:



        print(f"SELL ({len(sell)}):")



        for r in sell:



            # Why selling?



            if not r['passed']:



                reasons = []



                if not r['c1']: reasons.append('mom<=0')



                if not r['c2']: reasons.append('trend_break')



                if not r['c3']: reasons.append(f"dev>{a.max_dev}%")



                if not r.get('c4', True): reasons.append('atr_ratio<T')



                why = ', '.join(reasons)



            else:



                # Passed conditions but not in top5 (replaced by higher momentum)



                rank = next((i+1 for i, d in enumerate(qual) if d['code']==r['code']), 99)



                why = f"rank #{rank} out of top {a.top_n}, replaced by higher momentum"



            print(f"  SELL {r['code']} {r['name']:<16} mom={r['mom']*100:+.1f}% dev={r['dev']*100:.1f}% | {why}")







    if buy:



        print(f"\nBUY ({len(buy)}):")



        for r in buy:



            print(f"  BUY  {r['code']} {r['name']:<16} mom={r['mom']*100:+.1f}% dev={r['dev']*100:.1f}%")







    if not sell and not buy:



        print("  No trades needed. Current portfolio is optimal.")







    if not target and hs:



        print("\n  WARNING: No qualified picks. Consider liquidating all holdings.")







    # Save



    os.makedirs(OUTPUT_DIR, exist_ok=True)



    ts = datetime.now().strftime('%Y%m%d_%H%M%S')



    fp = os.path.join(OUTPUT_DIR, f'weekly_scan_v4_{ts}.json')



    with open(fp, 'w', encoding='utf-8') as f:



        json.dump({



            'ts': datetime.now().isoformat(),



            'params': {'ma_s': MA_S, 'ma_l': MA_L, 'lb': DEFAULT_LB,



                       'max_dev': a.max_dev, 'top_n': a.top_n},



            'total': len(etfs), 'ok': len(results), 'fail': failed,



            'qual': len(qual),



            'target': target, 'sell': sell, 'buy': buy, 'keep': keep,



            'all': results,



        }, f, ensure_ascii=False, indent=2)



    print(f"\nSaved: {fp}")











if __name__ == '__main__':



    main()







































