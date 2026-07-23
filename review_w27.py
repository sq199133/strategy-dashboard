import sys, os, json, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

# Load current scan result
scan_file = 'scan_results/weekly_scan_v4_20260627_163253.json'
with open(scan_file, encoding='utf-8') as f:
    data = json.load(f)

results = data.get('results', [])
print(f'Total results: {len(results)}')

# Show all qualified (passed) with scores
passed = [r for r in results if r.get('passed')]
print(f'Qualified (passed): {len(passed)}')

top = sorted(passed, key=lambda x: x.get('score', x.get('mom', 0)), reverse=True)[:15]
print(f'\nTop 15 by composite score:')
for i, r in enumerate(top, 1):
    sc = r.get('score', r.get('mom', 0))
    print(f'{i:2d}. {r["code"]:8s} {r["name"]:20s} score={sc:>8.2f} mom3w={r.get("mom","?"):>8.2f} dev={r.get("dev","?"):>6.1f} atr={r.get("atr","?"):>6.2f}')

# Check previous holdings
old_scans = sorted(glob.glob('scan_results/weekly_scan_v4_202*.json'))
pf_list = [s.split('\\')[-1] for s in old_scans[-3:]]
print(f'\nRecent scan files: {pf_list}')

if len(old_scans) >= 2:
    prev_file = old_scans[-2]
    pf = prev_file.split('\\')[-1]
    print(f'\nPrevious scan: {pf}')
    with open(prev_file, encoding='utf-8') as f:
        prev_data = json.load(f)
    prev_results = prev_data.get('results', [])
    prev_passed = [r for r in prev_results if r.get('passed')]
    prev_top = sorted(prev_passed, key=lambda x: x.get('score', x.get('mom', 0)), reverse=True)[:5]
    print('Previous Top 5:')
    for r in prev_top:
        sc = r.get('score', r.get('mom', 0))
        print(f'  {r["code"]:8s} {r["name"]:20s} score={sc:>8.2f}')

    current_codes = set(r['code'] for r in top[:3])
    prev_codes = set(r['code'] for r in prev_top[:3])
    
    keep = current_codes & prev_codes
    sell = prev_codes - current_codes
    new_buy = current_codes - prev_codes
    
    print(f'\n--- Change Analysis ---')
    print(f'Keep:    {keep}')
    print(f'Sell:    {sell}')
    print(f'New BUY: {new_buy}')
    
    # Get details of sell candidates
    if sell:
        print('\nSell details (from previous top 3):')
        for r in prev_top:
            if r['code'] in sell:
                sc = r.get('score', r.get('mom', 0))
                print(f'  {r["code"]:8s} {r["name"]:20s} score={sc:>8.2f}')
