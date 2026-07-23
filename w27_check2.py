import sys, os, json, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    f = f'data/history_long_v2/{code}.json'
    if not os.path.exists(f): return []
    with open(f, encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, dict): return d.get('records', [])
    return d

def get_last_n_weeks(recs, n=6):
    return [(r['w'], r['date'], r['close']) for r in recs[-n:]]

# Check key ETFs
etfs = [
    ('517850', '张江ETF(上周持仓1)'),
    ('588910', '科创价值ETF(上周持仓2)'),
    ('159572', '创业板200(上周持仓3)'),
    ('161127', '标普生物科技(新持仓1)'),
    ('512870', '杭州湾区ETF(新持仓2)'),
    ('161126', '标普医疗保健(新持仓3)'),
    ('000300', '沪深300'),
    ('510880', '红利ETF'),
    ('513100', '纳指ETF'),
    ('513290', '纳指生物科技'),
    ('159985', '能源化工ETF'),
    ('162411', '华宝油气'),
]

for code, name in etfs:
    recs = load_recs(code)
    if not recs:
        print(f'{code} {name}: NO FILE')
        continue
    last_n = get_last_n_weeks(recs, 6)
    print(f'\n{code} {name} (last={len(recs)}w, last_date={recs[-1]["date"]}):')
    for w, date, close in last_n:
        print(f'  {w} ({date}): {close}')

print('\n\n=== PREV HOLDINGS W26 PERFORMANCE (W24→W26) ===')
for code, name in [('517850', '张江ETF'), ('588910', '科创价值ETF'), ('159572', '创业板200')]:
    recs = load_recs(code)
    if len(recs) < 2: continue
    # Find W24 and W26
    w24 = next((r for r in recs if r['w'] == '2026-W24'), None)
    w26 = next((r for r in recs if r['w'] == '2026-W26'), None)
    if w24 and w26:
        chg = (w26['close'] - w24['close']) / w24['close'] * 100
        print(f'{code} {name}: W24={w24["close"]:.3f} → W26={w26["close"]:.3f} 2w={chg:>+6.1f}%')
    elif w26:
        print(f'{code} {name}: W24=missing, W26={w26["close"]:.3f}')

print('\n=== YTD ESTIMATE (W01→W26 cumulative for 2026) ===')
# Simple: sum of confirmed weekly changes for 2026 from backtest
# Backtest showed 2026 up to W24 = +7.9%
# Now need W25 and W26
# Let's estimate from current holdings
