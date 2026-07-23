import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'D:\QClaw_Trading\data\virtual_backtest_v2.json', encoding='utf-8') as f:
    d = json.load(f)

# 重新按策略统计交易
for strat_name, r in d['strategies'].items():
    if not r: continue
    trades = [t for t in d['all_trades'] if True]  # all trades
    
    # 截取该策略时间段的数据
    start = r['start_date']
    end = r['end_date']
    
    strat_trades = [t for t in d['all_trades'] if start <= t['buy_date'] <= end]
    
    # 但这里all_trades是全局的，无法区分来源。重新用backtest_v2的逻辑
    # 实际上backtest_v2返回的all_trades_global是按时间顺序混合的
    # 所以只能重新统计
    pass

# 正确做法：用策略各自的NAV历史来计算
print("策略表现对比（来自回测结果）：\n")
print(f"{'策略':<12} {'初始资金':>10} {'最终资金':>10} {'总收益':>8} {'年化':>7} {'交易':>5} {'胜率':>6} {'最大赢':>7} {'最大亏':>7} {'回测天数':>8}")
print("-"*90)
for strat_name, r in d['strategies'].items():
    if r:
        print(f"{strat_name:<12} {r['init_capital']:>10,.0f} {r['final_value']:>10,.0f} {r['total_return_pct']:>+7.1f}% {r['annual_return_pct']:>+6.1f}% {r['trade_count']:>5}次 {r['win_rate']:>5.0f}% {r['max_win']:>+6.1f}% {r['max_loss']:>+6.1f}% {r['backtest_days']:>7}天")

print("-"*90)
total_final = sum(r['final_value'] for r in d['strategies'].values() if r)
total_init = d['initial_capital']
total_ret = (total_final/total_init-1)*100
total_days = max(r['backtest_days'] for r in d['strategies'].values() if r)
annual = (total_final/total_init-1)*365/total_days*100
total_trades = sum(r['trade_count'] for r in d['strategies'].values() if r)
# Overall win rate from summary
owr = d['backtest_summary']['overall_win_rate']
print(f"{'合计':<12} {total_init:>10,.0f} {total_final:>10,.0f} {total_ret:>+7.1f}% {annual:>+6.1f}% {total_trades:>5}次 {owr:>5.0f}%")

print(f"\n回测区间: {d['backtest_summary']['start_date']} ~ {d['backtest_summary']['end_date']} (共{total_days}个交易日)")