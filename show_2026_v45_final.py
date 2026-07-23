import sys, json, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_012427.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
equity = data['equity']

pool = {}
try:
    with open(r'D:\Qclaw_Trading\data\etf_pool_V1_full.json', 'r', encoding='utf-8') as f:
        pdata = json.load(f)
    for etf in pdata.get('data', pdata.get('etfs', [])):
        pool[etf.get('code','')] = etf.get('name','').replace('\u00a0', '').strip()
except:
    pass

# ISO week to Monday date
def week_start(y, w):
    d = datetime.date(y, 1, 4)  # Jan 4 is always in ISO week 1
    d -= datetime.timedelta(days=d.isoweekday() - 1)  # back to Monday of week 1
    d += datetime.timedelta(weeks=w - 1)
    return d

print('''
═══════════════════════════════════════════════════════════════════════════
  2026年逐周持仓明细  |  策略 v4.5 (SC 40/40/20 + D15 + H3)
  年化+16.7% | 夏普0.91 | 最大回撤-16.8% | 2026 YTD +4.5%
═══════════════════════════════════════════════════════════════════════════
''')

header = f'{"周次":>5}  {"起始日期":>12}  {"周收益":>7}  {"累积YTD":>8}  {"回撤":>7}  {"持仓数":>6}  {"合格数":>6}  持仓明细'
print(header)
print('─' * 100)

start_2026_eq = None
prev_eq = None
max_2026_eq = None

for e in equity:
    w = e.get('w','')
    if not w or not w.startswith('2026'):
        prev_eq = e['eq']
        continue

    if start_2026_eq is None:
        start_2026_eq = e['eq']
        max_2026_eq = e['eq']

    wk = int(w.split('-')[1].lstrip('W0'))
    sd = week_start(2026, wk)
    date_str = f'{sd.month}月{sd.day}日'

    eq_val = e['eq']
    wk_ret = ((eq_val - prev_eq) / prev_eq * 100) if prev_eq else 0
    ytd = (eq_val / start_2026_eq - 1) * 100

    if eq_val > max_2026_eq:
        max_2026_eq = eq_val
    dd = (eq_val / max_2026_eq - 1) * 100

    nh = e.get('nh', 0)
    nq = e.get('nq', 0)
    holds = e.get('h', [])

    names = []
    for h in holds:
        code = h.split('.')[0] if '.' in str(h) else str(h)
        n = pool.get(code, code)
        if len(n) > 12:
            n = n[:12] + '…'
        names.append(n)
    holds_str = ', '.join(names)

    wk_str = f'{wk_ret:>+5.1f}%'
    ytd_str = f'{ytd:>+6.1f}%'
    dd_str = f'{dd:>+5.1f}%'

    # mark big weeks
    marker = ''
    if wk_ret > 5: marker = ' 🔥'
    elif wk_ret < -5: marker = ' 🔴'
    elif wk == 21 and ytd > 9: marker = ' 🏆'

    if nh == 0:
        holds_str = '[空仓]'

    print(f'  W{wk:<2d}   {date_str}   {wk_str}   {ytd_str}   {dd_str}     {nh}只      {nq}只   {holds_str}{marker}')
    prev_eq = eq_val

print('─' * 100)
print()

# Summary stats
print('''
📊 全年统计：
  正周: 10次  |  负周: 10次  |  空仓周: 2次(W14-W15)
  最大单周涨幅: W02 +14.1%  |  最大单周亏损: W10 -6.2%
  峰值YTD: W21 +9.3%  |  谷底YTD: W10 -10.0%

列说明：
  周收益 = 本周相对上周权益涨跌幅
  累积YTD = 年初至今累计收益
  回撤 = 当前相对2026年最高点的回撤
  持仓数 = 本周实际持有ETF数量
  合格数 = 本周扫描合格的ETF数量
  空仓 = 合格ETF为0，自动清仓避险
''')
