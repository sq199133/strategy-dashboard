import os, datetime, json

p = r'D:\QClaw_Trading\data\history_long\sz159786.json'
t = os.path.getmtime(p)
mtime = datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')
print('file last modified:', mtime)

with open(p, encoding='utf-8') as f:
    d = json.load(f)
recs = d.get('records', []) if isinstance(d, dict) else d
print('total records:', len(recs))
print('last 3 records:')
for r in recs[-3:]:
    print(' ', r)
