import json, sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\multi_strategy_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

strategies = ['布林带突破', '趋势突破', '均线交叉']

for s in strategies:
    etfs = data['strategy_selected'][s]
    print(f'\n=== 【{s}】共{len(etfs)}只 ===')
    for e in etfs:
        # e has keys: code, name, category, total_return, final_value, trade_count, win_rate, avg_return, max_win, max_loss
        print(f"  {e['code']} {e['name']} | 收益{e['total_return']:+.1f}% | 胜率{e['win_rate']:.0f}% | 交易{e['trade_count']}次 | 类别:{e['category']}")
    print()