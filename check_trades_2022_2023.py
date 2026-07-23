import json, glob, os

result_dir = r'D:\QClaw_Trading\backtest_results'
files = sorted(glob.glob(os.path.join(result_dir, 'bt_*.json')), key=os.path.getmtime)
latest = files[-1]

with open(latest) as f:
    data = json.load(f)

# 找trades
trades_key = None
for k in ['trades', 'trade_records', 'all_trades', 'transactions']:
    if k in data:
        trades_key = k
        break

if not trades_key:
    print(f'找不到trades key。顶层keys: {list(data.keys())}')
    # 打印前几个key的sample
    for k in list(data.keys())[:10]:
        v = data[k]
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
            print(f'{k}: [{len(v)}条] 字段={list(v[0].keys())}')
    exit()

trades = data[trades_key]
print(f'总交易: {len(trades)}条')

# 找2022-2023年交易
import re
date_keys = None
for t in trades:
    # 尝试找日期字段
    for dk in ['date', 'enter_date', 'exit_date', 'buy_date', 'sell_date', 'open_date', 'close_date', 'date_enter', 'date_exit', 'entry_date', 'exit_date']:
        if dk in t:
            date_keys = dk
            break
    if date_keys:
        break

if not date_keys:
    # 打印第一条字段
    print(f'第一条字段: {list(trades[0].keys())}')
    for k in trades[0]:
        print(f'  {k}: {trades[0][k]}')
    exit()

print(f'日期字段: {date_keys}')

# 按年份统计
from collections import defaultdict
yearly = defaultdict(lambda: {'buy': [], 'sell': [], 'hold': defaultdict(int)})

for t in trades:
    d = str(t.get(date_keys, ''))
    if len(d) < 4: continue
    yr = d[:4]
    if yr not in ['2022', '2023']: continue
    
    # 找code字段
    code = None
    for ck in ['code', 'symbol', 'etf', 'stock', 'name', 'ticker']:
        if ck in t:
            code = t[ck]
            break
    
    action = None
    for ak in ['action', 'type', 'direction', 'side']:
        if ak in t:
            action = str(t[ak]).lower()
            break
    
    if 'buy' in d.lower() or 'enter' in d.lower() or 'open' in d.lower():
        action = 'buy'
    elif 'sell' in d.lower() or 'exit' in d.lower() or 'close' in d.lower():
        action = 'sell'
    
    ret = t.get('ret', t.get('return', t.get('pnl', t.get('profit', 0))))
    
    yearly[yr]['trades'].append({
        'date': d[:10] if len(d) >= 10 else d,
        'code': code or '?',
        'action': action or '?',
        'ret': ret
    })

for yr in ['2022', '2023']:
    tds = yearly[yr]['trades']
    print(f'\n=== {yr}年交易 ({len(tds)}笔) ===')
    # 只看买入/持仓
    buys = [t for t in tds if t['action'] and 'sell' not in t['action'].lower() and 'exit' not in t['action'].lower()]
    sells = [t for t in tds if t['action'] and ('sell' in t['action'].lower() or 'exit' in t['action'].lower())]
    
    codes = {}
    for t in tds:
        c = t['code']
        if isinstance(c, str) and c not in codes:
            codes[c] = t['date']
    
    print(f'涉及ETF ({len(codes)}只):')
    for c, d in sorted(codes.items()):
        print(f'  {c} (首现: {d})')
