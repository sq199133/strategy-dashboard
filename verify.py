import json
with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    p = json.load(f)

total = 0
for name, s in p['strategies'].items():
    val = s['current_cash']
    for pos in s['positions']:
        val += pos['shares'] * pos['avg_cost']
    total += val
    held = ', '.join([f"{pos['code']}({pos['name']})@{pos['avg_cost']}" for pos in s['positions']]) or '空仓'
    print(f"  {name}: {s['current_cash']:,.0f}现金 | {held}")

print(f"  总资产: {total:,.2f} | 收益: {(total/p['initial_capital']-1)*100:+.2f}%")