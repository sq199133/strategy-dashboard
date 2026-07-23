import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

codes = ['517850','159572','159761','562800','159687','588220']
print('=== 原始数据检查（字段名=w, date） ===')
print()
for code in codes:
    f = f'./data/history_long_v2/{code}.json'
    if not os.path.exists(f):
        print(f'{code}: file not found')
        continue
    with open(f, encoding='utf-8') as fh:
        data = json.load(fh)
    recs = data['records']
    # Get last 10 weeks
    last10 = [(r['w'], r['date'], r['close']) for r in recs[-10:]]
    print(f'{code} {data.get("name","?")} ({len(recs)} records)')
    print(f'  Last 10 weeks:')
    for w, d, c in last10:
        print(f'    {w}  {d}  close={c:.3f}')
    # G3 from last completed week
    # Find the last week that is not the current partial week
    completed = [r for r in recs if not r['date'].startswith('2026-06-2') or r['date'] <= '2026-06-19']
    if len(completed) >= 3:
        c_last = completed[-1]
        c_prev = completed[-2]
        c_3prev = completed[-3]
        m1w = c_last['close'] / c_prev['close'] - 1
        m3w = c_last['close'] / c_3prev['close'] - 1
        g3_pass = m1w >= -0.01 and m3w >= 0
        g3_icon = 'PASS' if g3_pass else 'FAIL'
        print(f'  Last completed: {c_last["w"]} {c_last["date"]} close={c_last["close"]:.3f}')
        print(f'  Completed G3: M1W={m1w:+.2%}  M3W={m3w:+.2%} => {g3_icon}')
    print()

# Also check what filter_completed_weeks does
import weekly_scan_v4 as ws
print('=== filter_completed_weeks 效果 ===')
for code in ['517850', '159687']:
    wk = ws.load_weekly_file(code)
    if wk is None: continue
    print(f'{code}: 原始{len(wk)}条')
    filtered = ws.filter_completed_weeks(wk)
    print(f'  过滤后: {len(filtered)}条')
    if filtered:
        print(f'  最后一条: {filtered[-1]}')
    wk2 = ws.filter_completed_weeks(wk)
    print()
