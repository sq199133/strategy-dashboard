import json

with open(r'D:\QClaw_Trading\scan_results\weekly_scan_v4_20260606_213648.json', encoding='utf-8') as f:
    d = json.load(f)

for code in ['159786', '159732']:
    found = [x for x in d['all'] if x['code'] == code]
    if found:
        x = found[0]
        print(f"{code}  {x['name']}")
        print(f"  收盘: {x['close']}")
        print(f"  MA5:  {x['ma5']}")
        print(f"  MA21: {x['ma21']}")
        print(f"  动量: {x['mom']:+.2%}")
        print(f"  偏离: {x['dev']:+.2%}")
        print(f"  c1(动量>0): {x['c1']}  c2(均线多头): {x['c2']}  c3(偏离<=15%): {x['c3']}")
        print(f"  passed: {x['passed']}")
        print()
    else:
        print(f'{code} not found')
