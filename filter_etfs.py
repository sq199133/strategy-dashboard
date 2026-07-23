import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\virtual_backtest_v3.json', encoding='utf-8') as f:
    data = json.load(f)

# 剔除年化 < 10% 的ETF
MIN_ANNUAL = 10

for strat_name, r in data['strategies'].items():
    etfs = r['etf_results']
    removed = [e for e in etfs if e['annual_return_pct'] < MIN_ANNUAL]
    kept = [e for e in etfs if e['annual_return_pct'] >= MIN_ANNUAL]
    
    print(f"\n【{strat_name}】 {len(etfs)}只 → {len(kept)}只（剔除{len(removed)}只）")
    if removed:
        print("  ❌ 剔除:")
        for e in removed:
            print(f"    {e['code']} {e['name']:<18} 年化{e['annual_return_pct']:+.1f}% 胜率{e['win_rate']:.0f}%")
    for e in kept:
        print(f"    ✅ {e['code']} {e['name']:<18} 年化{e['annual_return_pct']:+.1f}% 胜率{e['win_rate']:.0f}%")