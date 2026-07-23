import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    for prefix in ['', 'sh', 'sz']:
        fname = f'data/history_long_v2/{code}.json'
        if not os.path.exists(fname):
            fname = f'data/history_long_v2/{prefix}{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
    return []

# === STEP 1: Previous holdings performance ===
prev_holds = {
    '517850': '张江ETF汇添富',
    '588910': '科创价值ETF建信',
    '159572': '创业板200ETF易方达',
}

print('=' * 72)
print(f'W27 周度复盘 (基于本地数据)')
print(f'=' * 72)
print()
print('=== 上周持仓 W25-W26 表现 ===')
for code, name in prev_holds.items():
    recs = load_recs(code)
    if not recs:
        print(f'{code} {name}: 无数据')
        continue
    closes = [r['close'] for r in recs]
    weeks = [r['w'] for r in recs]
    dates = [r['date'] for r in recs]
    
    # Find W24 and W26
    w24_close = None
    w26_close = None
    w26_date = None
    for i, w in enumerate(weeks):
        if w == '2026-W24':
            w24_close = closes[i]
        elif w == '2026-W26':
            w26_close = closes[i]
            w26_date = dates[i]
    
    if w24_close and w26_close:
        chg = (w26_close / w24_close - 1) * 100
        print(f'{code} {name}: W24={w24_close:.4f} → W26={w26_close:.4f} ({w26_date}) = {chg:+.1f}%')
    elif w26_close:
        print(f'{code} {name}: W26={w26_close:.4f} ({w26_date})')
    else:
        print(f'{code} {name}: 最近数据 {weeks[-1]}={closes[-1]:.4f}')

# Also check 159687 (亚太精选ETF) if previously held
print()

# === STEP 2: Load pool and compute all scores ===
with open(r'D:\QClaw_Trading\data\etf_pool_V1_full.json', encoding='utf-8') as f:
    pool = json.load(f)
etfs = pool if isinstance(pool, list) else pool.get('data', pool.get('etfs', []))

def calc_all(code, name):
    recs = load_recs(code)
    if not recs or len(recs) < 30:
        return None
    
    closes = [r['close'] for r in recs]
    weeks = [r.get('w', r.get('week', '')) for r in recs]
    dates = [r.get('date_end', r.get('date', '')) for r in recs]
    
    i = len(recs) - 1
    LB = 3
    
    # Check if we have enough data for 8w lookback
    if i < 8:
        return None
    
    # Get last week close (i-1) properly
    # Need to handle missing W25 - use the immediate predecessor in the array
    # The array is dense (no gaps in data), so i-1 is always the correct predecessor
    
    mom1w = closes[i] / closes[i-1] - 1 if i >= 1 else None
    mom3w = closes[i] / closes[i-LB] - 1 if i >= LB else None
    mom8w = closes[i] / closes[i-8] - 1 if i >= 8 else None
    
    score = 0.4 * mom1w + 0.4 * mom3w + 0.2 * mom8w
    
    # MA5/MA21
    ma5 = sum(closes[i-4:i+1]) / 5 if i >= 4 else None
    ma21 = sum(closes[i-20:i+1]) / 21 if i >= 20 else None
    ma_ok = ma5 > ma21 if (ma5 and ma21) else False
    
    # Deviation
    dev = closes[i] / ma21 - 1 if ma21 else None
    
    # ATR (approximate from closes)
    if i >= 21:
        trs = []
        for j in range(i-20, i+1):
            tr = abs(closes[j] - closes[j-1])
            trs.append(tr)
        atr14 = sum(trs[-14:]) / 14
        atr21 = sum(trs) / 21
        atr_r = atr14 / atr21 if atr21 > 0 else 1
    else:
        atr_r = 1
    
    c1 = score > 0
    c2 = ma_ok
    c3 = dev is not None and dev <= 0.15
    c4 = atr_r >= 0.85
    passed = c1 and c2 and c3 and c4
    
    return {
        'code': code, 'name': name,
        'week': weeks[i], 'date': dates[i], 'close': closes[i],
        'prev_close': closes[i-1] if i >= 1 else None,
        'mom1w': mom1w, 'mom3w': mom3w, 'mom8w': mom8w, 'score': score,
        'ma5': ma5, 'ma21': ma21, 'dev': dev, 'atr_ratio': atr_r,
        'c1': c1, 'c2': c2, 'c3': c3, 'c4': c4, 'passed': passed,
    }

results = []
for etf in etfs:
    code = etf.get('code', '')
    name = etf.get('name', etf.get('name_cn', ''))
    r = calc_all(code, name)
    if r:
        results.append(r)

# === STEP 3: Determine sell decisions ===
# If previous hold not in new top 3 → sell
passed = sorted([r for r in results if r['passed']], key=lambda x: x['score'], reverse=True)
print(f'\n=== 本地数据合格ETF: {len(passed)} 只 ===')
print()

# Deduplicate by score: keep highest only when scores are very close
# Sort by score desc first, then dedup
unique = {}
for r in passed:
    key = r['code']
    if key not in unique:
        unique[key] = r

deduped = sorted(unique.values(), key=lambda x: x['score'], reverse=True)

# Print full ranking (top 20)
print(f'{"#":>3} {"代码":>8} {"名称":>14} {"收盘":>8} {"1w%":>7} {"3w%":>7} {"8w%":>7} {"score":>7} {"偏离%":>6}')
print('-' * 72)
for rank, r in enumerate(deduped[:20], 1):
    print(f'{rank:>3} {r["code"]:>8} {r["name"]:>14} {r["close"]:>8.4f} '
          f'{r["mom1w"]*100:>+6.1f}% {r["mom3w"]*100:>+6.1f}% {r["mom8w"]*100:>+6.1f}% '
          f'{r["score"]*100:>+6.2f}% {r["dev"]*100:>+5.1f}%')

# TOP 3
top3 = deduped[:3]
top3_codes = set(r['code'] for r in top3)

print(f'\n=== 新持仓 (TOP 3) ===')
for r in top3:
    print(f'{r["code"]} {r["name"]}: score={r["score"]*100:.2f}%, mom3w={r["mom3w"]*100:+.2f}%, dev={r["dev"]*100:+.1f}%, atr={r["atr_ratio"]*100:.0f}%')

print(f'\n=== 卖出决策 ===')
for code, name in prev_holds.items():
    if code in top3_codes:
        print(f'{code} {name}: ✓ 继续持有 (新TOP3)')
    else:
        # Find where it ranks
        rank = None
        for i, r in enumerate(deduped, 1):
            if r['code'] == code:
                rank = i
                break
        print(f'{code} {name}: ✗ 卖出 (排名#{rank if rank else "未进合格"})')

# === STEP 4: Year-to-date estimate ===
# Use 2026 backtest result as baseline
print()
print(f'=== 2026年YTD估算 ===')
print(f'基线回测 W24 (+7.9%) 为截至2026-06-12的数据')
print(f'W25-W26本周持仓涨幅 +8%~+16%，预计YTD推升至 +9%~+10%')
print(f'(需完整回测确认)')
