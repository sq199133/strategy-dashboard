import os, json, glob

dir_path = r'D:\QClaw_Trading\data\history_long_v2'
files = glob.glob(os.path.join(dir_path, '*.json'))

pool_path = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
with open(pool_path, 'r', encoding='utf-8') as f:
    pool_data = json.load(f)
pool_etfs = list(set([item['code'].replace('sh','').replace('sz','') for item in pool_data['data']]))

print(f'history_long_v2 文件总数: {len(files)}')
print(f'V1_full池ETF数: {len(pool_etfs)}')

ok_count = 0
short_count = 0
fail_count = 0
min_row = 99999
max_row = 0
total_rows = 0
earliest_all = '9999'
latest_all = '0000'
errors = []

pool_downloaded_codes = []
row_counts = []

for fpath in files:
    code = os.path.basename(fpath).replace('.json','')
    bare = code.replace('sh','').replace('sz','')
    pool_downloaded_codes.append(bare)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        rows = len(data) / 2  # estimate: ~half are records, but actually the weekly file is flat
        # Actually weekly files are flat arrays
        rows = len(data)
        total_rows += rows
        row_counts.append(rows)
        if rows < 50:
            short_count += 1
        if rows >= 50:
            ok_count += 1
        min_row = min(min_row, rows)
        max_row = max(max_row, rows)
        if rows > 1:
            d0 = data[0].get('date','')
            d1 = data[-1].get('date','')
            if d0 and d0 < earliest_all:
                earliest_all = d0
            if d1 and d1 > latest_all:
                latest_all = d1
    except Exception as e:
        fail_count += 1
        errors.append((code, str(e)[:60]))

pool_downloaded = sum(1 for c in pool_etfs if c in pool_downloaded_codes)
pool_missing = [c for c in pool_etfs if c not in pool_downloaded_codes]

print(f'\n=== 下载质量 ===')
print(f'正常(>=50周): {ok_count}')
print(f'偏短(<50周): {short_count}')
print(f'解析失败: {fail_count}')
print(f'总行数: {total_rows}')
print(f'最小行数: {min_row}')
print(f'最大行数: {max_row}')
print(f'最早日期: {earliest_all}')
print(f'最新日期: {latest_all}')
if row_counts:
    row_counts.sort()
    p25 = row_counts[len(row_counts)//4]
    p50 = row_counts[len(row_counts)//2]
    p75 = row_counts[len(row_counts)*3//4]
    print(f'行数分布: 最小={row_counts[0]}, P25={p25}, P50={p50}, P75={p75}, 最大={row_counts[-1]}')

print(f'\n=== V1_full池覆盖 ===')
print(f'已下载: {pool_downloaded}/{len(pool_etfs)}')
if pool_missing:
    print(f'缺失: {len(pool_missing)}只:')
    for c in pool_missing[:20]:
        print(f'  {c}')

if errors:
    print(f'\n=== 解析错误 ===')
    for c, err in errors[:5]:
        print(f'  {c}: {err}')

print(f'\n=== 采样表现 ===')
samples = sorted(files, key=lambda f: os.path.getsize(f), reverse=True)[:5]
for fpath in samples:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    code = os.path.basename(fpath).replace('.json','')
    d0 = data[0].get('date','?')
    d1 = data[-1].get('date','?')
    print(f'{code}: {len(data)}周, {d0} ~ {d1}')
