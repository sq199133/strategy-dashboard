import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    p = json.load(f)

# 588170 止盈卖出 @2.425，两个策略都卖
sell_code = '588170'
sell_price = 2.425
sell_date = '2026-05-18'

for strat_name, strat in p['strategies'].items():
    new_positions = []
    for pos in strat['positions']:
        if pos['code'] == sell_code:
            shares = pos['shares']
            proceeds = round(shares * sell_price, 2)
            strat['current_cash'] = round(strat['current_cash'] + proceeds, 2)
            print(f"  止盈卖出: {strat_name} | {pos['code']} {pos['name']} {shares}股 @{sell_price} | 回款{proceeds:,.0f}元")
        else:
            new_positions.append(pos)
    strat['positions'] = new_positions

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'w', encoding='utf-8') as f:
    json.dump(p, f, ensure_ascii=False, indent=2)

# 验证
print()
total = 0
for name, s in p['strategies'].items():
    val = s['current_cash']
    for pos in s['positions']:
        val += pos['shares'] * pos['avg_cost']
    total += val
    held = ', '.join([f"{pos['code']}@{pos['avg_cost']}" for pos in s['positions']]) or '空仓'
    print(f"  {name}: {s['current_cash']:,.0f}现金 | 持仓: {held}")

print(f"  总资产(按成本): {total:,.0f}元")
