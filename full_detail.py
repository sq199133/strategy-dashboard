import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

# Load all ETF data from local files
import glob

etf_pool_file = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
with open(etf_pool_file, encoding='utf-8') as f:
    pool = json.load(f)

etfs = pool if isinstance(pool, list) else pool.get('data', pool.get('etfs', []))

print(f'Total in pool: {len(etfs)}')

# Load all weekly data
def load_recs(code):
    for prefix in ['', 'sh', 'sz']:
        fname = f'data/history_long_v2/{code}.json'
        if not os.path.exists(fname):
            fname = f'data/history_long_v2/{prefix}{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            recs = d.get('records', d) if isinstance(d, dict) else d
            return recs
    return []

def calc_all(code, name):
    recs = load_recs(code)
    if not recs or len(recs) < 30:
        return None
    
    closes = [r['close'] for r in recs]
    weeks   = [r.get('w', r.get('week', '')) for r in recs]
    dates   = [r.get('date_end', r.get('date', '')) for r in recs]
    
    i = len(recs) - 1
    LB = 3
    
    if i < 8:
        return None
    
    mom1w = closes[i] / closes[i-1] - 1
    mom3w = closes[i] / closes[i-LB] - 1
    mom8w = closes[i] / closes[i-8] - 1
    score = 0.4 * mom1w + 0.4 * mom3w + 0.2 * mom8w
    
    # MA5/MA21
    ma5_ok = sum(closes[i-4:i+1]) / 5 > sum(closes[i-20:i-4]) / 20 if i >= 20 else False
    ma5  = sum(closes[i-4:i+1]) / 5
    ma21 = sum(closes[i-20:i+1]) / 21
    ma_ok = ma5 > ma21
    
    # Deviation
    dev = closes[i] / ma21 - 1
    
    # ATR
    if i >= 21:
        trs = []
        for j in range(i-13, i+1):
            tr = max(closes[j]-closes[j-1], abs(closes[j]-closes[j+1]) if j+1 <= i else 0, abs(closes[j+1]-closes[j]) if j+1 <= i else 0) if j > 0 else 0
            trs.append(tr)
        atr14 = sum(trs[-14:]) / 14
        atr21_val = sum(trs) / 21
        atr_ratio = atr14 / atr21_val if atr21_val > 0 else 1
    else:
        atr_ratio = 1
    
    # Pass checks
    c1 = score > 0
    c2 = ma_ok
    c3 = dev <= 0.15
    c4 = atr_ratio >= 0.85
    passed = c1 and c2 and c3 and c4
    
    return {
        'code': code, 'name': name,
        'week': weeks[i], 'date': dates[i], 'close': closes[i],
        'mom1w': mom1w, 'mom3w': mom3w, 'mom8w': mom8w, 'score': score,
        'dev': dev, 'ma5': ma5, 'ma21': ma21,
        'atr_ratio': atr_ratio,
        'c1': c1, 'c2': c2, 'c3': c3, 'c4': c4, 'passed': passed,
        'LB': LB
    }

results = []
for etf in etfs:
    code = etf.get('code', '')
    name = etf.get('name', etf.get('name_cn', ''))
    r = calc_all(code, name)
    if r:
        results.append(r)

print(f'Calculated: {len(results)} / {len(etfs)}')

# Show all PASSED, sorted by score desc
passed = sorted([r for r in results if r['passed']], key=lambda x: x['score'], reverse=True)
print(f'\nPASSED: {len(passed)}')
print()
print(f'{"排名":>4} {"代码":>8} {"名称":>14} {"周":>10} {"收盘":>8} {"1w%":>7} {"3w%":>7} {"8w%":>7} {"score%":>7} {"偏离%":>6} {"ATR":>5}  {"MA5>MA21"}')
print('-'*110)
for rank, r in enumerate(passed, 1):
    ma_str = '✓' if r['c2'] else '✗'
    print(f'{rank:>4} {r["code"]:>8} {r["name"]:>14} {r["week"]:>10} {r["close"]:>8.4f} '
          f'{r["mom1w"]*100:>+6.1f}% {r["mom3w"]*100:>+6.1f}% {r["mom8w"]*100:>+6.1f}% '
          f'{r["score"]*100:>+6.2f}% {r["dev"]*100:>+5.1f}% {r["atr_ratio"]*100:>5.0f}%  {ma_str}')

print(f'\n→ TOP3（实际策略持仓）:')
for rank, r in enumerate(passed[:3], 1):
    print(f'  #{rank} {r["code"]} {r["name"]}: score={r["score"]*100:.2f}%, mom3w={r["mom3w"]*100:+.2f}%, dev={r["dev"]*100:+.1f}%')
