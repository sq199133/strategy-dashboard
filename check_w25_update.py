import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

for code in ['161127', '512870', '517850', '588910', '515580']:
    fname = f'data/history_long_v2/{code}.json'
    if not os.path.exists(fname):
        print(f'{code}: FILE NOT FOUND')
        continue
    with open(fname, encoding='utf-8') as f:
        d = json.load(f)
    recs = d.get('records', [])
    update = d.get('update', '?')
    weeks = [r['w'] for r in recs]
    
    # Find W25
    w25 = [r for r in recs if r['w'] == '2026-W25']
    last_w = weeks[-1]
    last_date = recs[-1].get('date', '?')
    
    print(f'{code}: update={update}  last_week={last_w}({last_date})')
    if w25:
        print(f'  W25 FOUND: date={w25[0]["date"]} close={w25[0]["close"]}')
    else:
        print(f'  W25: MISSING')
    
    # Show last 5
    print(f'  Last 5:')
    for r in recs[-5:]:
        print(f'    {r["w"]} ({r["date"]}) close={r["close"]}')
    print()
