import os
os.chdir(r'D:\Qclaw_Trading')

# Verify scan script
with open('weekly_scan_v4.py', encoding='utf-8') as f:
    c = f.read()
has_g3 = 'g3_pass' in c
print(f'weekly_scan_v4.py: G3={has_g3} (should be False)')

# Verify backtest defaults
with open('backtest_v5_qual_sizer.py', encoding='utf-8') as f:
    c = f.read()
for line in c.split('\n'):
    if 'mom1w-threshold' in line or 'mom3w-threshold' in line:
        print(f'backtest: {line.strip()}')

# Verify strategy doc
with open('strategy/周线动量策略_v4.5.md', encoding='utf-8') as f:
    c = f.read()
print(f"策略文档版本: {'v4.5.1' if '4.5.1' in c else 'v4.5 (need update)'}")
print(f"G3 in doc: {'removed (strikethrough)' if '已移除' in c else 'still active'}")

# Clean up temp scripts
for f in ['remove_g3.py', 'update_g3_defaults.py', 'update_strategy_doc.py']:
    if os.path.exists(f):
        print(f'Clean up: {f}')
