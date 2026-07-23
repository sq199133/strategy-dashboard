import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    f = f'data/history_long_v2/{code}.json'
    if not os.path.exists(f):
        print(f'  FILE NOT FOUND: {code}')
        return []
    with open(f, encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, dict):
        return d.get('records', [])
    return d

def calc_mom(cl, i, n):
    if i < n:
        return None
    return cl[i] / cl[i-n] - 1

def show_etf(code, name, show_weeks=10):
    recs = load_recs(code)
    if not recs:
        return
    closes = [r['close'] for r in recs]
    weeks   = [r['w']     for r in recs]
    dates   = [r['date']  for r in recs]

    LB = 3
    W1, W3, W8 = 0.4, 0.4, 0.2

    last_i = len(recs) - 1
    last_w = weeks[last_i]

    # Show last N weeks for reference
    print(f'\n{"="*72}')
    print(f'{code} {name}')
    print(f'最近 {show_weeks} 周收盘价 (用于核对计算):')
    print(f'  {"周":8s} {"日期":12s} {"收盘":>10s} {"1周前":>10s} {"3周前":>10s} {"8周前":>10s}')
    for i in range(max(0, last_i - show_weeks + 1), last_i + 1):
        w1_c = closes[i-1] if i >= 1 else None
        w3_c = closes[i-LB] if i >= LB else None
        w8_c = closes[i-8] if i >= 8 else None
        def fmt(c): return f'{c:.4f}' if c else 'N/A'
        print(f'  {weeks[i]:8s} {dates[i]:12s} {closes[i]:>10.4f}  {fmt(w1_c)}  {fmt(w3_c)}  {fmt(w8_c)}')

    # Final computation for last week
    i = last_i
    mom1w = calc_mom(closes, i, 1)
    mom3w = calc_mom(closes, i, LB)
    mom8w = calc_mom(closes, i, 8)
    score = W1 * mom1w + W3 * mom3w + W8 * mom8w

    print(f'\n最终计算 ({weeks[i]}, {dates[i]}, close={closes[i]:.4f}):')
    print(f'  mom1w = close[now] / close[1w ago] - 1')
    print(f'         = {closes[i]:.4f} / {closes[i-1]:.4f} - 1')
    print(f'         = {mom1w*100:+.4f}%')
    print(f'  mom3w = close[now] / close[3w ago] - 1  (LB={LB})')
    print(f'         = {closes[i]:.4f} / {closes[i-LB]:.4f} - 1')
    print(f'         = {mom3w*100:+.4f}%')
    print(f'  mom8w = close[now] / close[8w ago] - 1')
    print(f'         = {closes[i]:.4f} / {closes[i-8]:.4f} - 1')
    print(f'         = {mom8w*100:+.4f}%')
    print(f'  score = {W1}*mom1w + {W3}*mom3w + {W8}*mom8w')
    print(f'         = {W1}*{mom1w*100:.4f}% + {W3}*{mom3w*100:.4f}% + {W8}*{mom8w*100:.4f}%')
    print(f'         = {W1*mom1w*100:.4f}% + {W3*mom3w*100:.4f}% + {W8*mom8w*100:.4f}%')
    print(f'         = {score*100:.4f}%  (报告值: {score*100:.2f}%)')

for code, name in [
    ('161127', '标普生物科技LOF'),
    ('512870', '杭州湾区ETF南华'),
    ('161126', '标普医疗保健LOF'),
]:
    show_etf(code, name, show_weeks=10)
