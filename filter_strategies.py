import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

strategies = ['布林带突破', '趋势突破', '均线交叉']

# 筛选条件：交易>=15次，胜率>=50%，平均单次收益>=2%
FILTER = {
    'min_trades': 15,
    'min_win_rate': 50,
    'min_avg_return': 2.0,
    'min_total_return': 20.0  # 总收益至少20%
}

for s in strategies:
    suitable = []
    for e in data['all_results']:
        r = e.get(s)
        if not r: continue
        if (r['trade_count'] >= FILTER['min_trades'] and
            r['win_rate'] >= FILTER['min_win_rate'] and
            r['avg_return'] >= FILTER['min_avg_return'] and
            r['total_return'] >= FILTER['min_total_return']):
            
            # 综合评分 = 胜率 * log(1+总收益%) * sqrt(交易次数/15)
            import math
            score = r['win_rate'] * math.log(1 + r['total_return']) * math.sqrt(r['trade_count'] / 15)
            e_copy = e.copy()
            e_copy['_score'] = round(score, 2)
            e_copy['_r'] = r
            suitable.append(e_copy)
    
    suitable.sort(key=lambda x: x['_score'], reverse=True)
    
    print(f'\n=== 【{s}】筛选后 {len(suitable)} 只 ===')
    print(f"筛选条件：交易>=15次 | 胜率>=50% | 平均单次收益>=2% | 总收益>=20%")
    print(f"{'排名':<4} {'代码':<8} {'名称':<20} {'综合分':>6} {'历史收益':>8} {'胜率':>6} {'均次收益':>8} {'交易':>5} {'类别'}")
    print('-'*100)
    for i, e in enumerate(suitable, 1):
        r = e['_r']
        print(f"{i:<4} {e['code']:<8} {e['name']:<20} {e['_score']:>6.1f} {r['total_return']:>+7.1f}% {r['win_rate']:>5.0f}% {r['avg_return']:>+7.1f}% {r['trade_count']:>4}次  {e['category']}")