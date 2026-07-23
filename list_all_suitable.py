import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

strategies = ['布林带突破', '趋势突破', '均线交叉']

for s in strategies:
    all_etfs = data['all_results']
    suitable = []
    for e in all_etfs:
        r = e.get(s)
        if r and r['trade_count'] >= 3 and r['win_rate'] >= 50 and r['total_return'] > 0:
            suitable.append(e)
    suitable.sort(key=lambda x: x[s]['total_return'], reverse=True)
    
    print(f'\n=== 【{s}】适合的ETF 共{len(suitable)}只 ===')
    print(f"{'排名':<4} {'代码':<8} {'名称':<20} {'历史收益':>8} {'胜率':>6} {'交易次数':>7} {'类别'}")
    print('-'*90)
    for i, e in enumerate(suitable, 1):
        r = e[s]
        print(f"{i:<4} {e['code']:<8} {e['name']:<20} {r['total_return']:>+7.1f}% {r['win_rate']:>5.0f}% {r['trade_count']:>6}次  {e['category']}")