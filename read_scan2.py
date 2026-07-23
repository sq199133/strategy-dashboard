import json

with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260704_164149.json', encoding='utf-8') as f:
    data = json.load(f)

print('=== 562500 扫描精确数据 ===')
for etf in data['all']:
    if etf['code'] == '562500':
        print(f'  综合得分(score): {etf["score"]*100:.2f}%')
        print(f'  3周动量(mom):     {etf["mom"]*100:.2f}%')
        print(f'  1周动量(mom1w):   {etf["mom1w"]*100:.2f}%')
        print(f'  8周动量(mom8w):  {etf["mom8w"]*100:.2f}%')
        print(f'  偏离度(dev):     {etf["dev"]*100:.2f}%')
        print(f'  赛道(cat):       {etf["cat"]}')
        print(f'  通过所有过滤:    {etf["passed"]}')
        break

print()
print('=== TOP3 精确数据 ===')
for i, t in enumerate(data['target']):
    print(f'#{i+1} {t["code"]} {t["name"]} 赛道={t["cat"]} 得分={t["score"]*100:.2f}% 动量={t["mom"]*100:.2f}%')

print()
print('=== 得分排名（前15名且通过过滤的） ===')
all_sorted = sorted(data['all'], key=lambda x: x['score'], reverse=True)
rank = 1
for e in all_sorted:
    if e['passed']:
        print(f'{rank}. {e["code"]} 赛道={e["cat"]} 得分={e["score"]*100:.2f}% 3周动量={e["mom"]*100:.2f}%')
        rank += 1
        if rank > 15:
            break
