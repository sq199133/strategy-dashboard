import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
path = r'D:\QClaw_Trading\data\history\510300.json'
with open(path, encoding='utf-8') as f:
    raw = json.load(f)
if isinstance(raw, dict):
    records = raw.get('records', raw.get('data', [raw]))
else:
    records = raw
print(f'Total records: {len(records)}')
print(f'Keys: {list(records[0].keys())}')
print(f'Sample row: {records[0]}')
# Last row
print(f'Last row: {records[-1]}')
