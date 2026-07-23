import os, datetime, json

p = r'D:\QClaw_Trading\data\history_long\sz159786.json'
t = os.path.getmtime(p)
mtime = datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')
print(f'文件最后修改时间: {mtime}')

with open(p, encoding='utf-8') as f:
    d = json.load(f)
recs = d.get('records', []) if isinstance(d, dict) else d
print(f'记录数: {len(recs)}')
print('最后5条:')
for r in recs[-5:]:
    if isinstance(r, dict):
        print(f'  {r[\"date\"]}  close={r[\"close\"]}')
    else:
        print(f'  {r[0]}  close={r[2]}')
