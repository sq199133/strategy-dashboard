import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

# Check raw data for multiple ETFs
codes = ['517850','159572','159761','562800','159687','588220']
for code in codes:
    f = f'./data/history_long_v2/{code}.json'
    if not os.path.exists(f):
        print(f'{code}: file not found')
        continue
    with open(f, encoding='utf-8') as fh:
        data = json.load(fh)
    recs = data['records']
    print(f'{code} {data.get("name","?")} ({len(recs)} records)')
    print('  Last 8 records:')
    for r in recs[-8:]:
        print(f'    {r["week"]}  date_end={r.get("date_end","")}  close={r["close"]:.3f}')
    # Also compute G3 from raw
    if len(recs) >= 3:
        m1w = recs[-1]['close'] / recs[-2]['close'] - 1
        m3w = recs[-1]['close'] / recs[-3]['close'] - 1
        print(f'  Raw G3: M1W={m1w:+.2%}  M3W={m3w:+.2%}')
    print()
