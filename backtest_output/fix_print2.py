content = open('D:\\QClaw_Trading\\backtest_output\\factor_test_full.py', encoding='utf-8').read()
lines = content.split('\n')

# Find the problematic line
for i, line in enumerate(lines):
    if 'calmar' in line.lower() and "isinstance" in line:
        print(f"Found at line {i+1}")
        print(f"Original: {line}")

        replacement = """        c = res.get('calmar')
        if c is None or isinstance(c, str):
            calmar_str = 'N/A'
        else:
            calmar_str = f'{c:.2f}'
        print(f"{i+1:>4} {res['factor_name']:<18} {res['param_label']:<10} {res['top_k']:>5} {res['annual_return_pct']:>6.1f}% {res['sharpe']:>8.3f} {res['max_drawdown_pct']:>6.1f}% {calmar_str:>7} {res['win_rate_pct']:>5.1f}% {res['total_trades']:>5}")"""
        
        lines[i] = replacement
        break

content = '\n'.join(lines)
open('D:\\QClaw_Trading\\backtest_output\\factor_test_full.py', 'w', encoding='utf-8').write(content)
print("Done!")
