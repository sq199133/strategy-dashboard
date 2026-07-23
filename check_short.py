import json, os

data_dir = r'D:\Qclaw_Trading\data\history_long_v2'
short = []

for fn in sorted(os.listdir(data_dir)):
    if not fn.endswith('.json'):
        continue
    code = fn[:-5]
    data = json.load(open(os.path.join(data_dir, fn), encoding='utf-8'))
    rows = len(data) if isinstance(data, list) else len(data)
    if rows < 30:
        short.append((code, rows))

print(f"Files with <30 rows: {len(short)}")
for c, r in sorted(short):
    print(f"  {c}: {r} rows")
