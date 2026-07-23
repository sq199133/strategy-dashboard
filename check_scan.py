import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

with open('scan_results/weekly_scan_v4_20260627_163253.json', encoding='utf-8') as f:
    data = json.load(f)

print('Keys:', list(data.keys()))
print('Top-level keys/types:')
for k, v in data.items():
    if isinstance(v, list):
        print(f'  {k}: list[{len(v)}]')
    elif isinstance(v, dict):
        print(f'  {k}: dict with keys {list(v.keys())[:5]}')
    else:
        print(f'  {k}: {type(v).__name__} = {str(v)[:60]}')

# Check portfolio
if 'portfolio' in data:
    pf = data['portfolio']
    print(f'\nPortfolio: {pf}')
if 'target' in data:
    tg = data['target']
    print(f'Target: {tg}')
if 'qualified' in data:
    q = data['qualified']
    print(f'Qualified: {q}')
