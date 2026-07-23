import json, os

POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
HIST_DIR = r'D:\QClaw_Trading\data\history'
HIST_LONG = r'D:\QClaw_Trading\data\history_long'

with open(POOL_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)
etfs = data.get('data', data.get('etfs', []))

# Get all files in history dir
hist_files = set()
for fn in os.listdir(HIST_DIR):
    if fn.endswith('.json'):
        # Strip prefix
        code = fn.replace('sh', '').replace('sz', '')
        hist_files.add(code.replace('.json', ''))

# Check coverage
covered = []
missing = []
for etf in etfs:
    code = etf['code']
    # Check if in history
    in_hist = code in hist_files
    # Check if in history_long (with full-ish data = >365 days)
    in_hl = False
    for prefix in ['sh', 'sz', '']:
        path = os.path.join(HIST_LONG, f'{prefix}{code}.json')
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    recs = json.load(f)
                if len(recs) > 200:  # More than ~1 year
                    in_hl = True
                    break
            except:
                pass
    if in_hist:
        covered.append(code)
    elif in_hl:
        covered.append(code)  # Has some data in history_long
    else:
        missing.append(code)

print(f'Pool: {len(etfs)} ETFs')
print(f'Covered by history dir: {len([c for c in covered if c in hist_files])}')
print(f'Covered by history_long (>200 recs): {len([c for c in covered if c not in hist_files])}')
print(f'Missing (no good data): {len(missing)}')
print(f'\nMissing ETFs: {missing[:20]}')
