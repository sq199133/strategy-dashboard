import json, os, sys

data_dir = 'D:/QClaw_Trading/data/history/'
files = sorted(os.listdir(data_dir))

# classify all files
etf_starts = ('159','510','511','512','513','515','516','517','518','560','561','562','563','588')
etf_codes = [f[:-5] for f in files if f[:3] in etf_starts and f.endswith('.json')]
other_codes = [f[:-5] for f in files if f[:3] not in etf_starts and f != '000300.json' and f.endswith('.json')]

# check date coverage for each ETF
min_records = 50
valid_etfs = []
short_etfs = []
for code in etf_codes:
    path = os.path.join(data_dir, code + '.json')
    with open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    records = d.get('records', [])
    if len(records) >= min_records:
        valid_etfs.append((code, records[0]['date'], records[-1]['date'], len(records)))
    else:
        short_etfs.append((code, len(records)))

valid_etfs.sort(key=lambda x: x[1])

print(f"Total ETF-like files: {len(etf_codes)}")
print(f"Valid ETFs (>=50 records): {len(valid_etfs)}")
print(f"Short ETFs: {len(short_etfs)}")

# by start year
by_start_year = {}
for code, start, end, n in valid_etfs:
    year = int(start[:4])
    if year not in by_start_year:
        by_start_year[year] = []
    by_start_year[year].append(code)

print("\nFirst available year -> count of ETFs:")
for year in sorted(by_start_year.keys()):
    print(f"  {year}: {len(by_start_year[year])} ETFs")

print("\n5 oldest ETFs:")
for code, start, end, n in valid_etfs[:5]:
    print(f"  {code}: {start} ~ {end} ({n} records)")

print("\n5 newest ETFs:")
for code, start, end, n in valid_etfs[-5:]:
    print(f"  {code}: {start} ~ {end} ({n} records)")

# Common ETFs
print("\n=== Popular A-share ETFs ===")
common = ['510050','510300','510500','510880','510310','588000','159915','159949','159919','512100','512880','512000','512010','513100','518880','159845','159865','513050','159790','159766','159928']
for code in common:
    path = os.path.join(data_dir, code + '.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        records = d.get('records', [])
        name = d.get('name', '')
        codemeta = d.get('code', '')
        print(f"  {code}: code={codemeta}, name=[{name[:30]}], records={records[0]['date']} ~ {records[-1]['date']} ({len(records)})")

# latest year ETFs (2025+) for recent test
print("\n=== ETFs starting 2025+ ===")
recent = [(c,s,e,n) for c,s,e,n in valid_etfs if int(s[:4]) >= 2025]
print(f"Count: {len(recent)}")
for code, start, end, n in recent[:10]:
    print(f"  {code}: {start} ~ {end} ({n} records)")

# how many ETFs cover 2018+ (long history)
long_etfs = [(c,s,e,n) for c,s,e,n in valid_etfs if int(s[:4]) <= 2019]
print(f"\nETFs with history covering 2019 or earlier: {len(long_etfs)}")
