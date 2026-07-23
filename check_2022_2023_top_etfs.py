import json, glob, os

data_dir = r'D:\QClaw_Trading\data\history_long_v2'

# 计算每只ETF在2022、2023年的周线收益
years_analysis = {'2022': {}, '2023': {}}

files = glob.glob(os.path.join(data_dir, '*.json'))
print(f'扫描 {len(files)} 个文件...')

for fp in files:
    fname = os.path.basename(fp).replace('.json', '')
    try:
        with open(fp) as f:
            rows = json.load(f)
    except:
        continue
    
    if not rows or not isinstance(rows, list):
        continue
    
    # Ensure sorted by date
    def parse_date(r):
        d = r.get('date', r.get('w', ''))
        if isinstance(d, str) and len(d) >= 10:
            return d[:10]
        return str(d)[:10]
    
    # Filter to 2022 and 2023
    for yr in ['2022', '2023']:
        yr_rows = [r for r in rows if parse_date(r).startswith(yr)]
        if len(yr_rows) < 20:  # need enough weekly data
            continue
        
        # First and last close of the year
        first_close = yr_rows[0].get('close', yr_rows[0].get('c', 0))
        last_close = yr_rows[-1].get('close', yr_rows[-1].get('c', 0))
        if first_close and last_close and first_close > 0:
            ret = (last_close / first_close - 1) * 100
            years_analysis[yr][fname] = round(ret, 1)

for yr in ['2022', '2023']:
    items = sorted(years_analysis[yr].items(), key=lambda x: -x[1])
    print(f'\n=== {yr}年 收益TOP20 ETF ===')
    for code, ret in items[:20]:
        print(f'  {code}: {ret:+6.1f}%')
    # also show the negative ones
    neg = [x for x in items if x[1] < -10]
    print(f'  亏损>10%: {len(neg)}只 (最差: {neg[-1][0]} {neg[-1][1]:+.1f}%)')
