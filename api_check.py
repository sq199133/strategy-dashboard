import sys, os, json, urllib.request, urllib.parse, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def fetch_kline(code, days=200):
    # Try multiple prefixes
    prefixes = [code[:2], 'sh', 'sz']
    for pf in ['sh', 'sz', 'sh', 'sz']:
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
        except Exception as e:
            continue
    return None

codes = ['161127', '512870', '161126']
end_date = '2026-06-27'

for code in codes:
    kl = fetch_kline(code, days=50)
    if not kl:
        print(f'{code}: API fetch failed')
        continue
    
    # Find recent data around 2026-06-27
    recent = [(r[0], float(r[2]), float(r[1]), float(r[3]), float(r[4]), float(r[5])) 
              for r in kl if r[0] >= '2026-06-01']
    
    print(f'\n{code} API daily data (last 4 weeks):')
    for r in recent[-20:]:
        print(f'  {r[0]}: O={r[2]:.3f} C={r[1]:.3f} H={r[3]:.3f} L={r[4]:.3f} V={r[5]:.0f}')
    
    # Aggregate into weeks manually
    weeks = {}
    for r in kl:
        date = r[0]
        if date < '2026-01-01':
            continue
        # Week key: find the Friday of that week
        from datetime import datetime, timedelta
        d = datetime.strptime(date, '%Y-%m-%d')
        # Find the Monday of this week
        monday = d - timedelta(days=d.weekday())
        friday = monday + timedelta(days=4)
        wkey = friday.strftime('%Y-W%W')
        if wkey not in weeks:
            weeks[wkey] = {'open': float(r[2]), 'close': float(r[1]), 
                          'high': float(r[3]), 'low': float(r[4]), 'vol': float(r[5]),
                          'last_date': date}
        else:
            weeks[wkey]['close'] = float(r[1])
            weeks[wkey]['high'] = max(weeks[wkey]['high'], float(r[3]))
            weeks[wkey]['low'] = min(weeks[wkey]['low'], float(r[4]))
            weeks[wkey]['vol'] += float(r[5])
            weeks[wkey]['last_date'] = date

    # Show last few weeks
    sorted_weeks = sorted(weeks.items(), key=lambda x: x[1]['last_date'])
    print(f'\n  Aggregated weeks:')
    for wk, wv in sorted_weeks[-8:]:
        print(f'  {wk} ({wv["last_date"]}): O={wv["open"]:.3f} C={wv["close"]:.3f} H={wv["high"]:.3f} L={wv["low"]:.3f}')

    # Calculate mom values from API weekly data
    if len(sorted_weeks) >= 9:
        now_close = sorted_weeks[-1][1]['close']
        w1_close  = sorted_weeks[-2][1]['close']
        w3_close  = sorted_weeks[-4][1]['close']
        w8_close  = sorted_weeks[-9][1]['close']
        mom1w = now_close / w1_close - 1
        mom3w = now_close / w3_close - 1
        mom8w = now_close / w8_close - 1
        score = 0.4*mom1w + 0.4*mom3w + 0.2*mom8w
        print(f'\n  mom1w = {mom1w*100:+.2f}%  mom3w = {mom3w*100:+.2f}%  mom8w = {mom8w*100:+.2f}%  score = {score*100:.2f}%')
