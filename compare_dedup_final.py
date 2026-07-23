import json

with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260704_164149.json', encoding='utf-8') as f:
    data = json.load(f)

all_etfs = data['all']
qual = [e for e in all_etfs if e['passed']]

# 按_adj_score排序（和扫描脚本一致）
qual_sorted = sorted(qual, key=lambda x: x.get('_adj_score', x.get('score', x['mom'])), reverse=True)

# 有去重TOP3（当前策略）
cats = set()
dedup_top3 = []
for e in qual_sorted:
    c = e['cat'] or e['code']
    if c not in cats:
        cats.add(c)
        dedup_top3.append(e)
dedup_top3 = dedup_top3[:3]

# 无去重TOP3（直接取前3）
no_dedup_top3 = qual_sorted[:3]

print('=== 有去重 TOP3（当前策略）===')
for i, e in enumerate(dedup_top3):
    adj = e.get('_adj_score', e['score'])
    print(f'  {i+1}. {e["code"]} {e["name"]} 赛道={e["cat"]} 得分={e["score"]*100:.2f}% adj={adj*100:.2f}% C={e["c_pattern"]}')

print()
print('=== 无去重 TOP3（关掉赛道去重）===')
for i, e in enumerate(no_dedup_top3):
    adj = e.get('_adj_score', e['score'])
    print(f'  {i+1}. {e["code"]} {e["name"]} 赛道={e["cat"]} 得分={e["score"]*100:.2f}% adj={adj*100:.2f}% C={e["c_pattern"]}')

print()
print('=== 差异汇总 ===')
print(f'有去重: {" vs ".join([e["code"] for e in dedup_top3])}')
print(f'无去重: {" vs ".join([e["code"] for e in no_dedup_top3])}')
print()
print(f'562500 有去重: {"入选" if "562500" in [e["code"] for e in dedup_top3] else "未入选"}')
print(f'562500 无去重: {"入选" if "562500" in [e["code"] for e in no_dedup_top3] else "未入选"}')
print()
print(f'无去重时562500踢掉的是: {dedup_top3[2]["code"]} (得分{dedup_top3[2]["score"]*100:.2f}%)')
print(f'有去重时562500输给的是: {no_dedup_top3[0]["code"]} (adj得分{no_dedup_top3[0].get("_adj_score",no_dedup_top3[0]["score"])*100:.2f}%)')
