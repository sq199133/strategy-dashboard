import json, glob, os

result_dir = r'D:\QClaw_Trading\backtest_results'
files = sorted(glob.glob(os.path.join(result_dir, 'bt_*.json')), key=os.path.getmtime)
latest = files[-1]
print(f'加载: {latest}')

with open(latest) as f:
    data = json.load(f)

# Check structure
print(f'顶层keys: {list(data.keys())[:20]}')
print(f'逐年keys: {list(data.keys())[:30]}')

# 逐年
years = data.get('yearly_stats', data.get('years', []))
for y in years:
    yr = y.get('year', y.get('y'))
    ret = y.get('ret', y.get('total_return', y.get('annual_return', 0)))
    dd = y.get('max_dd', y.get('max_drawdown', 0))
    hp = y.get('hold_pct', y.get('hold_rate', y.get('in_market_pct', 0)))
    print(f'  {yr}: 收益={ret*100:+6.1f}%  DD={dd*100:+5.1f}%  持仓率={hp*100:.0f}%')
