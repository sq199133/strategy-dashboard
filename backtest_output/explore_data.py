import json, os

data_dir = 'D:/QClaw_Trading/data/history/'
files = sorted(os.listdir(data_dir))
n = len(files)
print(f'Total files: {n}')

# check ETF prefixes
etf_starts = ('159', '510', '511', '512', '513', '515', '516', '517', '518', '560', '561', '562', '563', '588')
etf_like = [f for f in files if f[:3] in etf_starts]
idx_like = [f for f in files if f[:3] in ('000', '399', '880', '931', '932', '950')]
other = [f for f in files if f not in etf_like and f not in idx_like]
print(f'ETF-like: {len(etf_like)}')
print(f'Index-like: {len(idx_like)}')
print(f'Other: {len(other)}')
print(f'ETF samples: {etf_like[:15]}')
print(f'Index samples: {idx_like[:15]}')
print(f'Other samples: {other[:15]}')

# check a few files
for f in ['159100.json', '510300.json', '588000.json', '000300.json']:
    path = os.path.join(data_dir, f)
    if not os.path.exists(path):
        print(f'{f}: NOT FOUND')
        continue
    with open(path) as fh:
        d = json.load(fh)
    records = d.get('records', [])
    start_date = records[0]['date'] if records else 'N/A'
    end_date = records[-1]['date'] if records else 'N/A'
    name_field = d.get('name', '')
    print(f'{f}: code={d.get("code")}, name=[{name_field[:20] if name_field else ""}], records={len(records)}, {start_date} ~ {end_date}')
