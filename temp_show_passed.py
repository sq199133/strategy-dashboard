import json

with open(r'D:\QClaw_Trading\scan_results\weekly_scan_v4_20260606_213648.json', encoding='utf-8') as f:
    d = json.load(f)

passed = [x for x in d['all'] if x['passed']]
print(f'合格数量: {len(passed)}')
print()
for x in passed:
    print(f"{x['code']}  {x['name']:<20}  cat={x['cat']}  动量={x['mom']:+.1%}  偏离={x['dev']:+.1%}")
