import sys, json, urllib.request
from datetime import datetime, timedelta
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def fetch_kline(code, days=50):
    for pf in ['sh', 'sz']:
        try:
            url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayhfq&param={code},'
                   f'day,,,{days},qfq&r=0.{os.times().system}%1000000')
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            raw = raw.split('=', 1)[-1]
            d = json.loads(raw)
            data = d.get('data', {}).get(code, {}).get('day', [])
            if not data:
                data = d.get('data', {}).get(code, {}).get('qfqday', [])
            if data:
                return data
        except:
            continue
    return None

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
        ww['d'].append(ds)
        ww['o'].append(float(o)); ww['c'].append(float(c))
        ww['h'].append(float(h)); ww['l'].append(float(l))
        ww['v'].append(float(v))
    out = []
    for k in sorted(weeks.keys()):
        ww = weeks[k]
        close = ww['c'][-1]  # last close in week
        date_end = ww['d'][-1]
        out.append({'week': k, 'date_end': date_end, 'close': close,
                    'open': ww['o'][0], 'high': max(ww['h']), 'low': min(ww['l'])})
    return out

import os

codes = ['161127', '512870', '161126']
for code in codes:
    kl = fetch_kline(code, days=60)
    if not kl:
        print(f'{code}: FAILED')
        continue
    wk = agg_weekly(kl)
    # Filter 2026 only, show last 12 weeks
    wk2026 = [w for w in wk if w['week'].startswith('2026')]
    print(f'\n=== {code} API Weekly (last 12 weeks) ===')
    for w in wk2026[-12:]:
        print(f"  {w['week']} ({w['date_end']}): close={w['close']:.4f}")

    # Compute mom for last week
    if len(wk2026) >= 9:
        i = len(wk2026) - 1
        now_c  = wk2026[i]['close']
        w1_c   = wk2026[i-1]['close']
        w3_c   = wk2026[i-3]['close']
        w8_c   = wk2026[i-8]['close']
        mom1w  = now_c / w1_c - 1
        mom3w  = now_c / w3_c - 1
        mom8w  = now_c / w8_c - 1
        score  = 0.4*mom1w + 0.4*mom3w + 0.2*mom8w
        print(f'\n  [{wk2026[i]["week"]}] mom1w={mom1w*100:+.2f}%  mom3w={mom3w*100:+.2f}%  mom8w={mom8w*100:+.2f}%  score={score*100:.2f}%')
        print(f'  Calculation: {0.4}*{mom1w*100:.2f}% + {0.4}*{mom3w*100:.2f}% + {0.2}*{mom8w*100:.2f}% = {score*100:.2f}%')
