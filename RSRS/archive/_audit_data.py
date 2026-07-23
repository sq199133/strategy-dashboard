"""数据完整性审计"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DATA = r'D:\QClaw_Trading\data\history'
codes = ['510050','510300','510500','512100','159915',
         '588000','513500','513100','518880','162411','515080']
names = {'510050':'上证50','510300':'沪深300','510500':'中证500',
         '512100':'中证1000','159915':'创业板','588000':'科创50',
         '513500':'标普500','513100':'纳斯达克','518880':'黄金',
         '162411':'原油','515080':'中证红利'}

print('=== ETF池数据审计 ===')
print(f'{"代码":<8} {"名称":<8} {"天数":<6} {"日期范围":<26} {"评估"}')
print('-'*55)

for code in codes:
    path = os.path.join(DATA, code+'.json')
    if not os.path.exists(path):
        print(f'{code:<8} {names[code]:<8} {"N/A":<6} {"文件不存在":<26} ❌ 缺失')
        continue
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    records = raw.get('records', raw.get('data', raw if isinstance(raw,list) else [raw]))
    dates = sorted(set(r.get('date',r.get('day','')) for r in records if r.get('date') or r.get('day')))
    if not dates:
        print(f'{code:<8} {names[code]:<8} {"?":<6} {"无日期":<26} ❌')
        continue
    n = len(records)
    rng = f'{dates[0][:10]} ~ {dates[-1][:10]}'
    
    if n < 200:
        status = f'⚠ 仅{n}天（需2100+天做完整回测）'
    elif n < 1200:
        status = f'⚡ 不足M=1200（{n}天，需完整5年历史）'
    else:
        status = '✅ 完整（含M=1200窗口）'
    
    print(f'{code:<8} {names[code]:<8} {n:<6} {rng:<26} {status}')

print()

# Check history_long_v2
print('=== history_long_v2 ===')
long_dir = r'D:\QClaw_Trading\data\history_long_v2'
if os.path.exists(long_dir):
    for code in codes:
        path = os.path.join(long_dir, code+'.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                raw = json.load(f)
            records = raw.get('records', raw.get('data', raw if isinstance(raw,list) else [raw]))
            dates = sorted(set(r.get('date',r.get('day','')) for r in records if r.get('date') or r.get('day')))
            n = len(records)
            if dates:
                print(f'  {code} {names[code]}: {n}条, {dates[0][:10]} ~ {dates[-1][:10]}')
else:
    print('  目录不存在')

# Check baostock_etf
print('\n=== baostock_etf ===')
baostock = r'D:\QClaw_Trading\data\baostock_etf'
if os.path.exists(baostock):
    files = os.listdir(baostock)
    print(f'  共{len(files)}个文件')
    for f in sorted(files)[:3]:
        print(f'  {f}')
else:
    print('  目录不存在')

# Check cache
print('\n=== cache ===')
cache = r'D:\QClaw_Trading\data\cache'
if os.path.exists(cache):
    files = os.listdir(cache)
    print(f'  共{len(files)}个文件')
    for f in sorted(files)[:3]:
        sz = os.path.getsize(os.path.join(cache,f))
        print(f'  {f} ({sz/1024:.0f}KB)')
else:
    print('  目录不存在')

# Check if there's a full historical dataset elsewhere
print('\n=== 搜索完整历史数据 ===')
search_dirs = [
    r'D:\QClaw_Trading\backtest_results',
    r'D:\QClaw_Trading\docs',
    r'C:\Users\Administrator\Desktop\ETF_data',
    r'C:\ETF_data',
]
for d in search_dirs:
    if os.path.exists(d):
        json_files = [f for f in os.listdir(d) if f.endswith('.json') and '510300' in f]
        if json_files:
            print(f'  {d}: {json_files[:3]}')
        else:
            # Check subdirectories
            for root, dirs, files in os.walk(d):
                for f in files:
                    if '510300' in f and f.endswith('.json'):
                        sz = os.path.getsize(os.path.join(root,f))
                        print(f'  找到: {os.path.join(root,f)} ({sz/1024:.0f}KB)')
                        break
print('  (搜索完成)')
