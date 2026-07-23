import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\candidate_pool_v4.json', 'r', encoding='utf-8') as f:
    v4 = json.load(f)

user_codes = {
    '布林带突破': set('159902 160723 161128 163208 501018 162719 512770 161130 159928 159819 162415 159996 512950 159985 159852'.split()),
    '趋势突破': set('160723 161129 159902 512770 161128 161130 512040 159928 159852 515580 162415 160719 160216 162719'.split()),
    '均线交叉': set('160723 560280 159667 588220 563300 159687'.split()),
}

print("=== 新发现（v4有，候选池没有）===\n")
for strat_name, strat_data in v4['results'].items():
    codes = user_codes[strat_name]
    new_etfs = [e for e in strat_data['etfs'] if e['code'] not in codes]
    new_etfs.sort(key=lambda x: x['annual_return'], reverse=True)
    print(f"【{strat_name}】新增 {len(new_etfs)}只（前10只）：")
    if new_etfs:
        for e in new_etfs[:10]:
            print(f"  {e['code']}  {e['name']:<18} 年化{e['annual_return']:+.1f}% 胜率{e['win_rate']:.0f}% {e['trade_count']}次 {e['start_date']}~{e['end_date']}")
    else:
        print("  无")
    print()