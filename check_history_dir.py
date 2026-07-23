import os, json, sys
from datetime import datetime, timedelta

dir_path = r'D:\QClaw_Trading\data\history'
files = [f for f in os.listdir(dir_path) if f.endswith('.json')]

results = []
for fname in files:
    fpath = os.path.join(dir_path, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and 'records' in data:
            records = data['records']
        else:
            continue
        if not records:
            continue
        d0 = records[0].get('date', records[0].get('day', ''))
        d1 = records[-1].get('date', records[-1].get('day', ''))
        earliest = min(d0, d1) if d0 and d1 else (d0 or d1 or '')
        latest = max(d0, d1) if d0 and d1 else (d0 or d1 or '')
        
        # Check if there are missing date fields in some records
        missing_dates = sum(1 for r in records if not r.get('date', r.get('day', '')))
        
        code = fname.replace('.json', '')
        results.append({
            'code': code,
            'rows': len(records),
            'earliest': str(earliest),
            'latest': str(latest),
            'missing_dates': missing_dates,
            'size_kb': round(os.path.getsize(fpath) / 1024, 1),
            'path': fpath
        })
    except Exception as e:
        results.append({
            'code': fname.replace('.json', ''),
            'rows': -1,
            'error': str(e)[:80]
        })

print('=== 1. 重复代码检查 (同一ETF有无前缀两份数据) ===')
codes_no_prefix = {}
for r in results:
    if r['rows'] < 0: continue
    code = r['code']
    # Normalize: strip sz/sh prefix
    bare = code
    for p in ['sz', 'sh']:
        if bare.startswith(p):
            bare = bare[len(p):]
    if bare not in codes_no_prefix:
        codes_no_prefix[bare] = []
    codes_no_prefix[bare].append(code)

dupes = {k: v for k, v in codes_no_prefix.items() if len(v) > 1}
print(f'发现 {len(dupes)} 个代码有重复文件:')
for bare, variants in sorted(dupes.items()):
    a = next(r for r in results if r['code'] == variants[0])
    b = next(r for r in results if r['code'] == variants[1])
    print(f'  {variants[0]} ({a["rows"]}行, {a["earliest"]}~{a["latest"]})')
    print(f'  {variants[1]} ({b["rows"]}行, {b["earliest"]}~{b["latest"]})')
    # Show size diff
    sz_diff = abs(a['size_kb'] - b['size_kb'])
    print(f'  大小差: {sz_diff}KB')
    print()

print('\n=== 2. 数据时效性检查 ===')
# What's the latest date across all files?
all_latest = [r['latest'] for r in results if r['rows'] > 0 and r['latest']]
if all_latest:
    newest = max(all_latest)
    print(f'全目录最新记录: {newest}')
    # Which files have data newer than 2026-06-01?
    fresh = [r for r in results if r['latest'] >= '2026-06-01']
    print(f'最新数据(>=2026-06-01): {len(fresh)}只')
    stale = [r for r in results if r['latest'] < '2026-06-01']
    print(f'过时数据(<2026-06-01): {len(stale)}只')
    for r in sorted(stale, key=lambda x: x['latest'])[:10]:
        print(f'  {r["code"]:15s} {r["rows"]:5d}行  {r["earliest"]} ~ {r["latest"]}')

print('\n=== 3. 数据间隔检查 (采样验证是否为日线) ===')
import random
samples = random.sample([r for r in results if r['rows'] > 500], min(5, len([r for r in results if r['rows'] > 500])))
for r in samples:
    with open(r['path'], 'r', encoding='utf-8') as f:
        data = json.load(f)
    recs = data if isinstance(data, list) else data.get('records', [])
    if len(recs) < 10: continue
    # Check date intervals in first 20 records
    dates = []
    for rec in recs[:30]:
        dt = rec.get('date', rec.get('day', ''))
        if dt: dates.append(dt)
    diffs = []
    for i in range(len(dates)-1):
        try:
            d1 = datetime.strptime(dates[i], '%Y-%m-%d')
            d2 = datetime.strptime(dates[i+1], '%Y-%m-%d')
            diffs.append(abs((d1-d2).days))
        except:
            pass
    if diffs:
        avg_gap = sum(diffs) / len(diffs)
        min_gap = min(diffs)
        max_gap = max(diffs)
        print(f'  {r["code"]}: {min_gap}~{max_gap}天间隔, 平均{avg_gap:.1f}天, 前10天: {dates[:10]}')

print('\n=== 4. 数据质量问题 ===')
# Check for files with very few rows
few_rows = [r for r in results if 0 < r['rows'] < 50]
print(f'行数<50的短线数据: {len(few_rows)}只')
for r in few_rows[:5]:
    print(f'  {r["code"]}: {r["rows"]}行 {r["earliest"]}~{r["latest"]}')

# Check for files with missing dates
missing = [r for r in results if r['missing_dates'] > 0]
print(f'\n缺少日期字段的记录: {len(missing)}只')
for r in missing[:3]:
    print(f'  {r["code"]}: {r["missing_dates"]}条缺少日期')

# Check parse errors
errors = [r for r in results if 'error' in r]
print(f'\n解析失败: {len(errors)}只')
for r in errors[:5]:
    print(f'  {r["code"]}: {r.get("error", "")}')

print('\n=== 5. 行数异常检测 ===')
# Check for unusually large files (possible index vs ETF)
from statistics import median, stdev
row_counts = [r['rows'] for r in results if r['rows'] > 0]
med = sorted(row_counts)[len(row_counts)//2]
print(f'行数中位数: {med}')
# Files with row count much higher than median might be indices
high = [r for r in results if r['rows'] > 4000]
print(f'行数>4000(可能是指数): {len(high)}只')
for r in high:
    print(f'  {r["code"]:15s} {r["rows"]:5d}行  {r["earliest"]}')

print('\n=== 6. V1_full池匹配检查 ===')
pool_path = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
with open(pool_path, 'r', encoding='utf-8') as f:
    pool_data = json.load(f)
pool_etfs = [item['code'].replace('sh','').replace('sz','') for item in pool_data['data']]
history_codes = []
for r in results:
    if r['rows'] < 0: continue
    c = r['code']
    for p in ['sz', 'sh']:
        if c.startswith(p):
            c = c[len(p):]
    history_codes.append(c)
history_set = set(history_codes)

# Check which V1 codes overlap with pre-2023 data
print('V1_full池中可用于完整回测(历史>=2020):')
pool_2020 = [c for c in pool_etfs if c in {r['code'].replace('sz','').replace('sh','') for r in results if r['rows'] >= 1000}]
print(f'  行数>=1000: {len(pool_2020)}/{len(pool_etfs)}')

pool_old = [c for c in pool_etfs if c in {r['code'].replace('sz','').replace('sh','') for r in results if r['earliest'] < '2020-01-01'}]
print(f'  可回溯到2020年前: {len(pool_old)}/{len(pool_etfs)}')
