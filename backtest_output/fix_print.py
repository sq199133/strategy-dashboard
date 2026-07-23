import re

content = open('D:\\QClaw_Trading\\backtest_output\\factor_test_full.py', encoding='utf-8').read()

# Find and replace the broken print line
# The problematic line has f-string with nested f-string for calmar
old = """        print(f\"{i+1:>4} {res['factor_name']:<18} {res['param_label']:<10} {res['top_k']:>5} {res['annual_return_pct']:>6.1f}% {res['sharpe']:>8.3f} {res['max_drawdown_pct']:>6.1f}% {res.get('calmar','N/A') if isinstance(res.get('calmar'),str) else f'{res.get(\"calmar\",0):>6.2f}':>7} {res['win_rate_pct']:>5.1f}% {res['total_trades']:>5})"""

new = """        c = res.get('calmar')
        if c is None or isinstance(c, str):
            calmar_str = 'N/A'
        else:
            calmar_str = f'{c:.2f}'
        print(f\"{i+1:>4} {res['factor_name']:<18} {res['param_label']:<10} {res['top_k']:>5} {res['annual_return_pct']:>6.1f}% {res['sharpe']:>8.3f} {res['max_drawdown_pct']:>6.1f}% {calmar_str:>7} {res['win_rate_pct']:>5.1f}% {res['total_trades']:>5}\")"""

if old in content:
    content = content.replace(old, new)
    open('D:\\QClaw_Trading\\backtest_output\\factor_test_full.py', 'w', encoding='utf-8').write(content)
    print('Fixed!')
else:
    print('Could not find exact pattern. Searching...')
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'calmar' in line.lower() and 'isinstance' in line.lower():
            print(f'Line {i+1}: {repr(line)}')
            break
    else:
        for i, line in enumerate(lines):
            if 'calmar' in line.lower() and 'f{' in line:
                print(f'Line {i+1}: {line[:100]}...')
