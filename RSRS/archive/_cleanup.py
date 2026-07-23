import os
cur = r'D:\QClaw_Trading\RSRS\current'
to_delete = [
    os.path.join(cur, '策略说明书_v3.md'),
    os.path.join(cur, 'final_strategy_v2.md'),
]
for f in to_delete:
    if os.path.exists(f):
        os.remove(f)
        print(f'Deleted: {os.path.basename(f)}')
    else:
        print(f'Not found: {os.path.basename(f)}')

print('Done')
