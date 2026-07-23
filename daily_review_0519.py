import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    p = json.load(f)

# 2026-05-19 收盘价（从neodata实时查询）
prices = {
    '159996': {'name': '家电ETF国泰',  'close': 1.554, 'prev_close': 1.560},
    '501225': {'name': '全球芯片LOF T+1', 'close': 3.704, 'prev_close': 3.842},
    '159902': {'name': '中小100ETF华夏', 'close': 5.105, 'prev_close': 5.044},
}

print("="*70)
print("📊 虚拟盘日报 — 2026-05-19（周二）")
print("="*70)

total_asset = 0
actions = []

for strat_name, strat in p['strategies'].items():
    cash = strat['current_cash']
    strat_value = cash
    held = []
    
    print(f"\n{'─'*70}")
    print(f"【{strat_name}】现金: {cash:,.0f}元")
    
    if not strat['positions']:
        print(f"  空仓")
    else:
        print(f"  {'代码':<8} {'名称':<16} {'持仓':>6} {'成本':>7} {'今收':>7} {'浮盈亏':>8} {'收益率':>7} {'日涨跌':>6}")
        print(f"  {'-'*62}")
        
        for pos in strat['positions']:
            code = pos['code']
            shares = pos['shares']
            avg_cost = pos['avg_cost']
            
            if code in prices:
                cur = prices[code]['close']
                prev = prices[code]['prev_close']
            else:
                cur = avg_cost
                prev = avg_cost
            
            cost_val = shares * avg_cost
            cur_val = shares * cur
            pnl = cur_val - cost_val
            pnl_pct = (cur / avg_cost - 1) * 100
            day_chg = (cur / prev - 1) * 100
            
            strat_value += cur_val
            held.append((code, pos['name'], shares, avg_cost, cur, pnl, pnl_pct, day_chg))
            
            flag = "🟢" if pnl > 0 else "🔴"
            print(f"  {flag} {code:<8} {pos['name']:<16} {shares:>6}股 {avg_cost:>7.3f} {cur:>7.3f} {pnl:>+8.0f}元 {pnl_pct:>+6.1f}% {day_chg:>+5.1f}%")
    
    strat_pnl = strat_value - strat['allocated_capital']
    strat_pnl_pct = (strat_value / strat['allocated_capital'] - 1) * 100
    total_asset += strat_value
    
    print(f"  策略资产: {strat_value:,.0f}元 | 浮盈亏: {strat_pnl:>+,.0f}元 ({strat_pnl_pct:>+,.1f}%)")

# 止损止盈检查
print(f"\n{'='*70}")
print("⚠️ 止损/止盈检查")
print(f"{'='*70}")

sold_today = []
for strat_name, strat in p['strategies'].items():
    new_positions = []
    for pos in strat['positions']:
        code = pos['code']
        if code in prices:
            cur = prices[code]['close']
            avg = pos['avg_cost']
            chg = (cur / avg - 1) * 100
            if chg <= -8:
                shares = pos['shares']
                proceeds = round(shares * cur, 2)
                print(f"  🔴 触发止损! {strat_name} | {code} {pos['name']} 亏损{chg:+.1f}% → 卖出@{cur}")
                actions.append(('止损卖出', strat_name, pos['name'], code, cur, shares, proceeds))
                strat['current_cash'] = round(strat['current_cash'] + proceeds, 2)
            elif chg >= 15:
                shares = pos['shares']
                proceeds = round(shares * cur, 2)
                print(f"  🟢 触发止盈! {strat_name} | {code} {pos['name']} 盈利{chg:+.1f}% → 卖出@{cur}")
                actions.append(('止盈卖出', strat_name, pos['name'], code, cur, shares, proceeds))
                strat['current_cash'] = round(strat['current_cash'] + proceeds, 2)
            else:
                new_positions.append(pos)
        else:
            new_positions.append(pos)
    strat['positions'] = new_positions

if not actions:
    print("  无触发")

# 保存
with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'w', encoding='utf-8') as f:
    json.dump(p, f, ensure_ascii=False, indent=2)

# 总览
print(f"\n{'='*70}")
print("📋 总资产概览")
print(f"{'='*70}")
total_pnl = total_asset - 50000
total_pct = (total_asset / 50000 - 1) * 100
print(f"  初始资金: 50,000元")
print(f"  当前总资产: {total_asset:,.0f}元")
print(f"  总浮盈亏: {total_pnl:>+,.0f}元 ({total_pct:>+,.2f}%)")

if actions:
    print(f"\n  今日操作:")
    for a in actions:
        print(f"    {a[0]}: {a[1]} | {a[2]} {a[4]}元 × {a[5]}股 = {a[6]:,.0f}元")