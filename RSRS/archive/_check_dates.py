import json, os, warnings
warnings.filterwarnings('ignore')
import sys
sys.stdout.reconfigure(encoding='utf-8')

codes = ['510050','510300','510500','512100','159915',
         '588000','513500','513100','518880','162411','515080']

print("=== ETF 数据最新日期 ===")
for c in codes:
    path = rf'D:\QClaw_Trading\data\history\{c}.json'
    if not os.path.exists(path):
        print(f'  {c}: ❌ MISSING')
        continue
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    records = raw.get('records', raw.get('data', raw if isinstance(raw, list) else [raw]))
    last3 = [r.get('date', r.get('day', '?'))[:10] for r in records[-5:]]
    print(f'  {c}: last={last3[-1]}  last5={last3}')
