import json, os

data_file = r'D:\QClaw_Trading\data\history_long_v2\562500.json'
with open(data_file, encoding='utf-8') as f:
    content = f.read().strip()
    obj = json.loads(content)
records = obj.get('records', [])
print(f'总记录数: {len(records)}')
print(f'ETF名称: {obj.get("name", "unknown")}')
print(f'最后20条周线:')
for r in records[-20:]:
    print(f"  {r['date']}  close={r['close']}  vol={r.get('vol',0)}")
