import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

# Check actual date format in files
with open('data/history_long_v2/517850.json', encoding='utf-8') as f:
    d = json.load(f)
recs = d.get('records', [])
print(f'517850 records: {len(recs)}')
print(f'Last 5 dates:')
for r in recs[-5:]:
    print(f'  {r}')

print()
with open('data/history_long_v2/000300.json', encoding='utf-8') as f:
    d2 = json.load(f)
recs2 = d2.get('records', [])
print(f'000300 records: {len(recs2)}')
print(f'Last 5 dates:')
for r in recs2[-5:]:
    print(f'  {r}')
