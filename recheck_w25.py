import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    for prefix in ['', 'sh', 'sz']:
        fname = f'data/history_long_v2/{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
        fname = f'data/history_long_v2/{prefix}{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
    return []

# Check all weekly records for 161127 around W24-W26
print('=== 161127 全部周线记录（最后12条）===')
recs = load_recs('161127')
print(f'总记录数: {len(recs)}')
print()
for r in recs[-12:]:
    print(f"  {r['w']} date={r.get('date',r.get('date_end','?'))} close={r['close']}")

print()
print('=== 512870 全部周线记录（最后12条）===')
recs2 = load_recs('512870')
for r in recs2[-12:]:
    print(f"  {r['w']} date={r.get('date',r.get('date_end','?'))} close={r['close']}")

print()
print('=== 517850 全部周线记录（最后12条）===')
recs3 = load_recs('517850')
for r in recs3[-12:]:
    print(f"  {r['w']} date={r.get('date',r.get('date_end','?'))} close={r['close']}")
