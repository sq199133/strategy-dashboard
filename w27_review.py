import sys, os, json, math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_weekly(code):
    """Load weekly data from history_long_v2"""
    f = f'data/history_long_v2/{code}.json'
    if not os.path.exists(f):
        return None
    with open(f, encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, dict):
        recs = d.get('records', [])
    else:
        recs = d
    return recs

def find_weeks(recs, year, week_str):
    """Find week data by year-week string like '2026-W26'"""
    for r in recs:
        date = r.get('date_end', r.get('date', ''))
        if date.startswith(year) and f'-W{week_str}' in date:
            return r
    return None

# Previous holdings
prev_holdings = [
    {'code': '517850', 'name': '张江ETF汇添富', 'cat': '科技'},
    {'code': '588910', 'name': '科创价值ETF建信', 'cat': '科创'},
    {'code': '159572', 'name': '创业板200ETF易方达', 'cat': '创业板'},
]

# Current new holdings
curr_holdings = [
    {'code': '161127', 'name': '标普生物科技LOF', 'cat': '美股/生物'},
    {'code': '512870', 'name': '杭州湾区ETF南华', 'cat': '区域'},
    {'code': '161126', 'name': '标普医疗保健LOF', 'cat': '美股/医疗'},
]

print('=== W26 PRICE CHANGES (上周持仓周涨跌) ===')
print('(W26: 2026-06-19 ~ 2026-06-26)')
for h in prev_holdings:
    recs = load_weekly(h['code'])
    if not recs:
        print(f'{h["code"]} {h["name"]}: NO DATA')
        continue
    # Find W25 and W26
    w25 = find_weeks(recs, '2026', 'W25')
    w26 = find_weeks(recs, '2026', 'W26')
    if w25 and w26:
        pct = (w26['close'] - w25['close']) / w25['close'] * 100
        print(f'{h["code"]} {h["name"]:15s}: W25={w25["close"]:.3f} W26={w26["close"]:.3f} Change={pct:>+6.1f}%')
    elif not w25 and w26:
        # W25 might be missing, compare W24 and W26
        w24 = find_weeks(recs, '2026', 'W24')
        if w24:
            pct = (w26['close'] - w24['close']) / w24['close'] * 100
            print(f'{h["code"]} {h["name"]:15s}: W24={w24["close"]:.3f} W26={w26["close"]:.3f} 2w_chg={pct:>+6.1f}% (W25 missing)')
        else:
            print(f'{h["code"]} {h["name"]}: Only W26={w26["close"]:.3f}')
    else:
        print(f'{h["code"]} {h["name"]}: W25={w25} W26={w26}')

print()
print('=== CURRENT TOP 5 QUALIFIED (本周合格候选TOP5) ===')
# Load current scan
with open('scan_results/weekly_scan_v4_20260627_163253.json', encoding='utf-8') as f:
    curr = json.load(f)

curr_top = sorted([r for r in curr['all'] if r.get('passed')], 
                  key=lambda x: x.get('score', x.get('mom', 0)), reverse=True)[:10]
for i, r in enumerate(curr_top, 1):
    sc = r.get('score', r.get('mom', 0))
    mom = r.get('mom', 0) * 100
    mom1 = r.get('mom1w', 0) * 100
    mom8 = r.get('mom8w', 0) * 100
    dev = r.get('dev', 0) * 100
    atr = r.get('atr', 0)
    print(f'{i:2d}. {r["code"]:8s} {r["name"]:18s} score={sc:>7.2f} mom3w={mom:>+6.1f}% mom1w={mom1:>+5.1f}% mom8w={mom8:>+5.1f}% dev={dev:>5.1f}% atr={atr:.2f}')

print()
print('=== W26 MARKET CONTEXT (上周市场) ===')
# Check major indices
indices = [
    ('000300', '沪深300'),
    ('510300', '沪深300ETF'),
    ('510880', '红利ETF'),
    ('159915', '创业板ETF'),
    ('513100', '纳指ETF'),
    ('162411', '华宝油气'),
]
for code, name in indices:
    recs = load_weekly(code)
    if not recs:
        continue
    w24 = find_weeks(recs, '2026', 'W24')
    w25 = find_weeks(recs, '2026', 'W25')
    w26 = find_weeks(recs, '2026', 'W26')
    if w24 and w25 and w26:
        chg24 = (w25['close'] - w24['close']) / w24['close'] * 100
        chg25 = (w26['close'] - w25['close']) / w25['close'] * 100
        print(f'{code} {name:12s}: W24={w24["close"]:>8.3f} W25={w25["close"]:>8.3f}({chg24:>+5.1f}%) W26={w26["close"]:>8.3f}({chg25:>+5.1f}%)')
    elif w25 and w26:
        chg = (w26['close'] - w25['close']) / w25['close'] * 100
        print(f'{code} {name:12s}: W25={w25["close"]:>8.3f} W26={w26["close"]:>8.3f}({chg:>+5.1f}%)')

print()
print('=== 2026 YTD UPDATE ===')
# Run partial year backtest for YTD
# From backtest: 2026 up to W24 = +7.9% (already in backtest)
# Need to add W25 and W26
# Let's estimate: W25-W26 contribution from previous holdings + new position effect
