import json, sys
sys.stdout.reconfigure(encoding='utf-8')

for code, name in [('159996','家电ETF国泰'),('159902','中小100ETF华夏')]:
    for prefix in ['sh','sz']:
        path = f'D:\\QClaw_Trading\\data\\history\\{prefix}{code}.json'
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            recs = sorted(data['records'], key=lambda x: x['date'])
            last = recs[-1]
            prev = recs[-2]
            print(f"{code} {name}: 周四={prev['close']} 周五={last['close']} ({last['date']})")
        except:
            pass