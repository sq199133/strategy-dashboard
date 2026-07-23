import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    p = json.load(f)

# 2026-05-18 收盘价（从neodata实时查询）
prices = {
    '159996': {'name': '家电ETF国泰', 'close': 1.560, 'prev_close': 1.567},
    '501225': {'name': '全球芯片LOF T+1', 'close': 3.842, 'prev_close': 3.938},
    '588170': {'name': '科创半导体ETF华夏', 'close': 2.425, 'prev_close': 2.415},
    '159902': {'name': '中小100ETF华夏', 'close': 5.044, 'prev_close': 5.050},
}

print("="*70)
print("📊 虚拟盘日报 — 2026-05-18（周一）")
print("="*70)

total_asset = 0
total_cost = 0

for strat_name, strat in p['strategies'].items():
    cash = strat['current_cash']
    strat_value = cash
    strat_cost = 0
    
    print(f"\n{'─'*70}")
    print(f"【{strat_name}】资金: {cash:,.0f}元")
    
    if not strat['positions']:
        print(f"  空仓 | 策略资产: {cash:,.0f}元")
    else:
        print(f"  {'代码':<8} {'名称':<16} {'持仓':>6} {'成本':>7} {'现价':>7} {'浮盈亏':>8} {'收益率':>7} {'日涨跌':>6}")
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
            strat_cost += cost_val
            
            flag = "🟢" if pnl > 0 else "🔴"
            print(f"  {flag} {code:<8} {pos['name']:<16} {shares:>6}股 {avg_cost:>7.3f} {cur:>7.3f} {pnl:>+8.0f}元 {pnl_pct:>+6.1f}% {day_chg:>+5.1f}%")
    
    strat_pnl = strat_value - strat['allocated_capital']
    strat_pnl_pct = (strat_value / strat['allocated_capital'] - 1) * 100
    total_asset += strat_value
    total_cost += strat['allocated_capital']
    
    print(f"  策略资产: {strat_value:,.0f}元 | 浮盈亏: {strat_pnl:>+,.0f}元 ({strat_pnl_pct:>+,.1f}%)")

# 止损止盈检查
print(f"\n{'='*70}")
print("⚠️ 止损/止盈检查")
print(f"{'='*70}")
for strat_name, strat in p['strategies'].items():
    for pos in strat['positions']:
        code = pos['code']
        if code in prices:
            cur = prices[code]['close']
            avg = pos['avg_cost']
            chg = (cur / avg - 1) * 100
            if chg <= -8:
                print(f"  🔴 触发止损! {strat_name} | {code} {pos['name']} 亏损{chg:+.1f}%")
            elif chg >= 15:
                print(f"  🟢 触发止盈! {strat_name} | {code} {pos['name']} 盈利{chg:+.1f}%")

# 总览
print(f"\n{'='*70}")
print("📋 总资产概览")
print(f"{'='*70}")
total_pnl = total_asset - 50000
total_pct = (total_asset / 50000 - 1) * 100
print(f"  初始资金: 50,000元")
print(f"  当前总资产: {total_asset:,.0f}元")
print(f"  总浮盈亏: {total_pnl:>+,.0f}元 ({total_pct:>+,.2f}%)")
