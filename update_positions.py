import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    p = json.load(f)

# 布林带突破：买501225 @3.472 和 588170 @1.968
bb = p['strategies']['布林带突破']
# 501225 全球芯片LOF
shares_501225 = int(5556 / 3.472 * 0.995)  # 1592股
cost_501225 = shares_501225 * 3.472
bb['positions'].append({
    "code": "501225", "name": "全球芯片LOF T+1",
    "shares": shares_501225, "avg_cost": 3.472,
    "buy_date": "2026-05-15", "signal": "布林带突破"
})
# 588170 科创半导体ETF
shares_588170 = int(5556 / 1.968 * 0.995)  # 2809股
cost_588170 = shares_588170 * 1.968
bb['positions'].append({
    "code": "588170", "name": "科创半导体ETF华夏",
    "shares": shares_588170, "avg_cost": 1.968,
    "buy_date": "2026-05-15", "signal": "布林带突破"
})
# 更新现金
bb['current_cash'] = round(bb['current_cash'] - cost_501225 - cost_588170, 2)

# 趋势突破：买588170 @1.968 和 501225 @3.472
td = p['strategies']['趋势突破']
# 588170
td['positions'].append({
    "code": "588170", "name": "科创半导体ETF华夏",
    "shares": shares_588170, "avg_cost": 1.968,
    "buy_date": "2026-05-15", "signal": "趋势突破"
})
# 501225
td['positions'].append({
    "code": "501225", "name": "全球芯片LOF T+1",
    "shares": shares_501225, "avg_cost": 3.472,
    "buy_date": "2026-05-15", "signal": "趋势突破"
})
td['current_cash'] = round(td['current_cash'] - cost_588170 - cost_501225, 2)

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'w', encoding='utf-8') as f:
    json.dump(p, f, ensure_ascii=False, indent=2)

# 验证
total = 0
for name, s in p['strategies'].items():
    val = s['current_cash']
    for pos in s['positions']:
        val += pos['shares'] * pos['avg_cost']
    total += val
    print(f"{name}: {s['current_cash']:,.0f}现金 | {len(s['positions'])}持仓")
    for pos in s['positions']:
        print(f"  {pos['code']} {pos['name']} {pos['shares']}股 @{pos['avg_cost']}")
print(f"总资产: {total:,.2f} | 收益: {(total/p['initial_capital']-1)*100:+.2f}%")
print(f"\n✅ 已更新持仓记录")