import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    for prefix in ['', 'sh', 'sz']:
        fname = f'data/history_long_v2/{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
        fname = f'data/history_long_v2/{prefix}{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
    return []

def calc(code, name):
    recs = load_recs(code)
    if not recs or len(recs) < 30:
        return None
    closes = [r['close'] for r in recs]
    weeks = [r.get('w', '') for r in recs]
    dates = [r.get('date_end', r.get('date', '')) for r in recs]
    i = len(recs) - 1
    
    # W26 is the last (current week)
    # W25 is i-1
    # W23 is i-3 (3 weeks back)
    # W18 is i-8 (8 weeks back)
    
    # Get the 8-week-back index
    # We need at least 8 records before W26
    if i < 8:
        return None
    
    w26_c = closes[i]
    w25_c = closes[i-1]
    w23_c = closes[i-3]
    w18_c = closes[i-8]
    
    mom1w = w26_c / w25_c - 1
    mom3w = w26_c / w23_c - 1
    mom8w = w26_c / w18_c - 1
    score = 0.4 * mom1w + 0.4 * mom3w + 0.2 * mom8w
    
    # MA5/MA21 (use closes[-5] through closes[0] = W26 to W22 for MA5)
    ma5 = sum(closes[i-4:i+1]) / 5
    ma21 = sum(closes[i-20:i+1]) / 21
    ma_ok = ma5 > ma21
    
    dev = w26_c / ma21 - 1
    
    # ATR from closes (approximation)
    trs = [abs(closes[j] - closes[j-1]) for j in range(i-20, i+1) if j > 0]
    atr14 = sum(trs[-14:]) / 14
    atr21 = sum(trs) / 21 if trs else 1
    atr_r = atr14 / atr21 if atr21 > 0 else 1
    
    c1 = score > 0
    c2 = ma_ok
    c3 = dev <= 0.15
    c4 = atr_r >= 0.85
    passed = c1 and c2 and c3 and c4
    
    return {
        'code': code, 'name': name,
        'week': weeks[i], 'date': dates[i],
        'w26': w26_c, 'w25': w25_c, 'w23': w23_c, 'w18': w18_c,
        'mom1w': mom1w, 'mom3w': mom3w, 'mom8w': mom8w, 'score': score,
        'ma5': ma5, 'ma21': ma21, 'dev': dev, 'atr_r': atr_r,
        'c1': c1, 'c2': c2, 'c3': c3, 'c4': c4, 'passed': passed,
        'LB': 3
    }

# Load pool
with open(r'D:\QClaw_Trading\data\etf_pool_V1_full.json', encoding='utf-8') as f:
    pool = json.load(f)
etfs = pool if isinstance(pool, list) else pool.get('data', pool.get('etfs', []))

results = []
for etf in etfs:
    code = etf.get('code', '')
    name = etf.get('name', etf.get('name_cn', ''))
    r = calc(code, name)
    if r:
        results.append(r)

passed = sorted([r for r in results if r['passed']], key=lambda x: x['score'], reverse=True)

# Deduplicate
seen = {}
for r in passed:
    if r['code'] not in seen:
        seen[r['code']] = r
top3 = list(seen.values())[:3]

top3_codes = set(r['code'] for r in top3)

print('=' * 72)
print('W27 完整复盘（数据已更新：W25 present）')
print('=' * 72)
print()

print('=== 上周持仓 W25→W26 涨跌 ===')
prev_holds = [('517850', '张江ETF汇添富'), ('588910', '科创价值ETF建信'), ('159572', '创业板200ETF易方达')]
for code, name in prev_holds:
    r_data = calc(code, name)
    if r_data:
        chg = (r_data['w26'] / r_data['w25'] - 1) * 100
        action = '留' if code in top3_codes else '卖'
        print(f'  {code} {name}: {r_data["w25"]:.4f} → {r_data["w26"]:.4f} ({r_data["week"]}) = {chg:+.1f}%  [{action}]')

print()
print(f'=== 合格ETF {len(passed)} 只（基于完整W25数据）===')
print()
print(f'{"#":>3} {"代码":>8} {"名称":>14} {"W25":>7} {"W26":>7} {"1w%":>7} {"3w%":>7} {"8w%":>7} {"score":>7} {"偏离%":>6}  c1/c2/c3/c4')
print('-' * 95)
for rank, r in enumerate(list(seen.values())[:20], 1):
    flags = f"{'✓' if r['c1'] else '✗'}/{'✓' if r['c2'] else '✗'}/{'✓' if r['c3'] else '✗'}/{'✓' if r['c4'] else '✗'}"
    print(f'{rank:>3} {r["code"]:>8} {r["name"]:>14} {r["w25"]:>7.4f} {r["w26"]:>7.4f} '
          f'{r["mom1w"]*100:>+6.1f}% {r["mom3w"]*100:>+6.1f}% {r["mom8w"]*100:>+6.1f}% '
          f'{r["score"]*100:>+6.2f}% {r["dev"]*100:>+5.1f}%  {flags}')

print()
print('=== 新持仓 TOP 3（逐行计算）===')
for rank, r in enumerate(top3, 1):
    print(f'\n#{rank} {r["code"]} {r["name"]}:')
    print(f'  W26({r["date"]}) close={r["w26"]:.4f}')
    print(f'  W25({r["mom1w"]*0+r["w25"]:.4f}) ← 前复权close')  # Just placeholder
    print(f'  mom1w = {r["w26"]:.4f}/{r["w25"]:.4f}-1 = {r["mom1w"]*100:+.2f}%')
    print(f'  mom3w = {r["w26"]:.4f}/{r["w23"]:.4f}-1 = {r["mom3w"]*100:+.2f}%')
    print(f'  mom8w = {r["w26"]:.4f}/{r["w18"]:.4f}-1 = {r["mom8w"]*100:+.2f}%')
    print(f'  score = 0.4×{r["mom1w"]*100:.2f}% + 0.4×{r["mom3w"]*100:.2f}% + 0.2×{r["mom8w"]*100:.2f}% = {r["score"]*100:.2f}%')
    print(f'  MA5={r["ma5"]:.4f} MA21={r["ma21"]:.4f} dev={r["dev"]*100:+.2f}% ATR={r["atr_r"]:.2f}')
    print(f'  过滤: c1(score>0)={"✓" if r["c1"] else "✗"} c2(MA5>MA21)={"✓" if r["c2"] else "✗"} c3(dev≤15%)={"✓" if r["c3"] else "✗"} c4(ATR≥0.85)={"✓" if r["c4"] else "✗"} → PASSED={r["passed"]}')

print()
print('=== 持仓操作汇总 ===')
for code, name in prev_holds:
    if code in top3_codes:
        print(f'  {code} {name}: ✓ 继续持有')
    else:
        print(f'  {code} {name}: ✗ 卖出')
for r in top3:
    if r['code'] not in dict(prev_holds):
        print(f'  {r["code"]} {r["name"]}: ★ 买入 (score={r["score"]*100:.2f}%)')
