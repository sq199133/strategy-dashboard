import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

# Check if there are daily records for June 15-18 in the file
# The weekly file stores weekly aggregated data, but maybe it also has daily records
# Let's check the raw structure of 161127

with open(r'D:\Qclaw_Trading\data\history_long_v2\161127.json', encoding='utf-8') as f:
    raw = f.read()

# Check if it's a dict with 'records' or a list
d = json.loads(raw)
print(f'Type: {type(d)}')
if isinstance(d, dict):
    print(f'Keys: {list(d.keys())}')
    for k in d.keys():
        v = d[k]
        if isinstance(v, list):
            print(f'  {k}: list of {len(v)} items')
            if v:
                print(f'    first: {v[0]}')
                print(f'    last: {v[-1]}')
        elif isinstance(v, str):
            print(f'  {k}: {v[:100]}')
        else:
            print(f'  {k}: {str(v)[:100]}')
else:
    print(f'List of {len(d)} items')
    print(f'First: {d[0]}')
    print(f'Last: {d[-1]}')

print()
print('=== All records near the gap (W24 → W26) ===')
if isinstance(d, dict):
    if 'records' in d:
        recs = d['records']
    else:
        # It's a dict, maybe with dates as keys?
        recs = list(d.values())[0] if d.values() else []
else:
    recs = d

# Show last 15 records
for r in recs[-15:]:
    print(f"  {r}")
