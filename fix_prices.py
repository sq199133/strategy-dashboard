import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    p = json.load(f)

# 布林带突破：159996 家电ETF国泰 @1.567
bb = p['strategies']['布林带突破']
for pos in bb['positions']:
    if pos['code'] == '159996':
        pos['avg_cost'] = 1.567
        pos['buy_date'] = '2026-05-15'
        pos['shares'] = int(5556 / 1.567 * 0.995)
        cost = pos['shares'] * 1.567
        pos['shares'] = int(5556 / 1.567 * 0.995)  # keep precise

# 趋势突破：159902 中小100ETF华夏 @5.05
td = p['strategies']['趋势突破']
for pos in td['positions']:
    if pos['code'] == '159902':
        pos['avg_cost'] = 5.05
        pos['buy_date'] = '2026-05-15'
        pos['shares'] = int(5556 / 5.05 * 0.995)

# 重新计算
for strat in p['strategies'].values():
    cash = strat['current_cash']
    strat_value = 0
    for pos in strat['positions']:
        cost = pos['shares'] * pos['avg_cost']
        cash -= cost
        strat_value += cost
    cash += strat['current_cash'] - sum(pos['shares'] * pos['avg_cost'] for pos in strat['positions'])
    strat['current_cash'] = round(16667 - sum(pos['shares'] * pos['avg_cost'] for pos in strat['positions']), 2)

# 修正：直接重置现金
bb['current_cash'] = round(16667 - 3551 * 1.567, 2)
td['current_cash'] = round(16667 - 1100 * 5.05, 2)

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'w', encoding='utf-8') as f:
    json.dump(p, f, ensure_ascii=False, indent=2)

print("更新后:")
for name, strat in p['strategies'].items():
    for pos in strat['positions']:
        shares = pos['shares']
        price = pos['avg_cost']
        cost = shares * price
        print(f"  {name} | {pos['code']} {pos['name']} | {shares}股 @{price} | 成本:{cost:,.2f} | 剩余:{strat['current_cash']:,.2f}")