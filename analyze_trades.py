import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'D:\QClaw_Trading\data\virtual_backtest_v2.json', encoding='utf-8') as f:
    d = json.load(f)

trades = d['all_trades']
completed = [t for t in trades if t['reason'] in ['止损', '止盈', '信号卖出']]

for strat_name in ['布林带突破', '趋势突破', '均线交叉']:
    by_strat = [t for t in completed if t['return_pct'] > 0]
    by_strat.sort(key=lambda x: x['return_pct'], reverse=True)
    
    wins = [t for t in completed if t['return_pct'] > 0]
    losses = [t for t in completed if t['return_pct'] <= 0]
    
    print(f'\n=== 【{strat_name}】交易统计 ===')
    print(f'总交易: {len(completed)}次 | 盈利: {len(wins)}次 | 亏损: {len(losses)}次 | 胜率: {len(wins)/len(completed)*100:.0f}%')
    print(f'平均收益: {sum(t["return_pct"] for t in completed)/len(completed):.1f}%')
    print(f'最大盈利: {max(t["return_pct"] for t in completed):.1f}% | 最大亏损: {min(t["return_pct"] for t in completed):.1f}%')
    
    # 按止损/止盈/信号卖出分类
    for reason in ['止盈', '止损', '信号卖出']:
        rs = [t for t in completed if t['reason'] == reason]
        if rs:
            print(f'  {reason}: {len(rs)}次 | 平均收益: {sum(t["return_pct"] for t in rs)/len(rs):.1f}%')
    
    print(f'\n  TOP5盈利:')
    for t in wins[:5]:
        print(f'    {t["code"]} {t["name"]:<16} {t["return_pct"]:+.1f}% @{t["sell_price"]:.3f} [{t["reason"]}]')
    
    print(f'\n  TOP5亏损:')
    losses_sorted = sorted(losses, key=lambda x: x['return_pct'])[:5]
    for t in losses_sorted:
        print(f'    {t["code"]} {t["name"]:<16} {t["return_pct"]:+.1f}% @{t["sell_price"]:.3f} [{t["reason"]}]')