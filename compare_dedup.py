import json

with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260704_164149.json', encoding='utf-8') as f:
    data = json.load(f)

# qual = all ETFs that passed all filters
qual = [e for e in data['all'] if e['passed']]
print(f'通过所有过滤的ETF: {len(qual)}只')
print()

# 模拟无去重的TOP3（按得分排序取前3）
qual_sorted = sorted(qual, key=lambda x: x['score'], reverse=True)
top3_no_dedup = qual_sorted[:3]

print('=== 有去重 TOP3（当前策略） ===')
dedup_cats = set()
i = 0
for e in qual_sorted:
    c = e['cat'] or e['code']
    if c not in dedup_cats:
        dedup_cats.add(c)
        print(f"  {i+1}. {e['code']} {e['name']} 赛道={e['cat']} 得分={e['score']*100:.2f}% 动量={e['mom']*100:.2f}%")
        i += 1
        if i >= 3:
            break

print()
print('=== 无去重 TOP3（关掉赛道去重） ===')
for i, e in enumerate(top3_no_dedup):
    print(f"  {i+1}. {e['code']} {e['name']} 赛道={e['cat']} 得分={e['score']*100:.2f}% 动量={e['mom']*100:.2f}%")

print()
print('=== 对比 ===')
print(f'有去重TOP3: 机器人562500 不在赛道里被挤掉')
print(f'无去重TOP3: 机器人562500 直接第1名入选')
print()
print('562500如果入选，会替代哪只？')
d3 = top3_no_dedup[2]
d2 = top3_no_dedup[1]
d1 = top3_no_dedup[0]
print(f'无去重第3名: {d3["code"]} {d3["name"]} 赛道={d3["cat"]} 得分={d3["score"]*100:.2f}%')
print(f'有去重第3名: 515920 智能消费 得分=5.30%')
print()
print(f'结论: 562500(8.80%) > 515920(5.30%)，无去重下562500直接踢掉515920')
