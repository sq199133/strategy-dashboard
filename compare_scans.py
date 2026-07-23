import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

# Load previous scan
with open('scan_results/weekly_scan_v4_20260623_203631.json', encoding='utf-8') as f:
    prev = json.load(f)

# Load current scan
with open('scan_results/weekly_scan_v4_20260627_163253.json', encoding='utf-8') as f:
    curr = json.load(f)

print('=== PREVIOUS SCAN (2026-06-23, W26) ===')
print(f'Total: {prev["total"]} OK: {prev["ok"]} Qual: {prev["qual"]} Dedup: {prev["dedup"]}')
print(f'Target: {[r["code"] for r in prev["target"]]}')
print(f'Buy: {[r["code"] for r in prev["buy"]]}')
print(f'Sell: {[r["code"] for r in prev["sell"]]}')
print(f'Keep: {[r["code"] for r in prev["keep"]]}')
print(f'Holdings in all[]: {sum(1 for r in prev["all"] if r.get("holding"))}')

# Show top 10 from prev
prev_top = sorted([r for r in prev["all"] if r.get('passed')], key=lambda x: x.get('score', x.get('mom',0)), reverse=True)[:10]
print('\nPrev top 10:')
for r in prev_top:
    sc = r.get('score', r.get('mom', 0))
    print(f'  {r["code"]:8s} {r["name"]:18s} score={sc:>8.4f} hold={r.get("holding")}')

print(f'\n=== CURRENT SCAN (2026-06-27, W27) ===')
print(f'Total: {curr["total"]} OK: {curr["ok"]} Qual: {curr["qual"]} Dedup: {curr["dedup"]}')
print(f'Target: {[r["code"] for r in curr["target"]]}')
print(f'Buy: {[r["code"] for r in curr["buy"]]}')
print(f'Sell: {[r["code"] for r in curr["sell"]]}')
print(f'Holdings in all[]: {sum(1 for r in curr["all"] if r.get("holding"))}')

curr_top = sorted([r for r in curr["all"] if r.get('passed')], key=lambda x: x.get('score', x.get('mom',0)), reverse=True)[:10]
print('\nCurr top 10:')
for r in curr_top:
    sc = r.get('score', r.get('mom', 0))
    print(f'  {r["code"]:8s} {r["name"]:18s} score={sc:>8.4f} hold={r.get("holding")}')

# Check dedup top 5
curr_dedup = sorted([r for r in curr["all"] if r.get('passed')], key=lambda x: x.get('score', x.get('mom',0)), reverse=True)[:5]
print(f'\nTop 5 after dedup:')
for r in curr_dedup:
    sc = r.get('score', r.get('mom', 0))
    print(f'  {r["code"]:8s} {r["name"]:18s} score={sc:>8.4f}')

# Compare
prev_codes = set(r['code'] for r in prev['target'])
curr_codes = set(r['code'] for r in curr['target'])
print(f'\n=== PORTFOLIO CHANGE ===')
print(f'Prev: {prev["target"][0]["code"]} / {prev["target"][1]["code"]} / {prev["target"][2]["code"]}')
print(f'Curr: {curr["target"][0]["code"]} / {curr["target"][1]["code"]} / {curr["target"][2]["code"]}')
print(f'Stay: {prev_codes & curr_codes}')
print(f'Out:  {prev_codes - curr_codes}')
print(f'In:   {curr_codes - prev_codes}')
