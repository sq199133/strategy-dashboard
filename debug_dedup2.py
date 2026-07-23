import json

with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260704_164149.json', encoding='utf-8') as f:
    data = json.load(f)

all_etfs = data['all']
qual = [e for e in all_etfs if e['passed']]

# 按_adj_score排序（和扫描脚本一致）
qual_sorted = sorted(qual, key=lambda x: x.get('_adj_score', x.get('score', x['mom'])), reverse=True)

print(f'=== qual_sorted前15名（按_adj_score排序）===')
for i, e in enumerate(qual_sorted[:15]):
    adj = e.get('_adj_score', e.get('score', e['mom']))
    print(f'{i+1:2d}. {e["code"]} {e["name"]:<12s} cat={e["cat"]:<16s} score={e["score"]*100:.2f}% adj={adj*100:.2f}%')

print()
# 模拟dedup
cats = set()
dedup_list = []
for e in qual_sorted:
    c = e['cat'] or e['code']
    if c not in cats:
        cats.add(c)
        dedup_list.append(e)

print('=== dedup后的完整列表（8只）===')
for i, e in enumerate(dedup_list):
    print(f'{i+1}. {e["code"]} {e["name"]:<12s} cat={e["cat"]:<16s} score={e["score"]*100:.2f}%')

print()
print('=== 实际扫描的TARGET ===')
for i, t in enumerate(data['target']):
    print(f'{i+1}. {t["code"]} {t["name"]:<12s} cat={t["cat"]:<16s} score={t["score"]*100:.2f}%')

print()
print('=== 差异分析 ===')
print('我的本地计算dedup top3:', [e['code'] for e in dedup_list[:3]])
print('实际扫描的target top3:', [t['code'] for t in data['target']])
print()
print('562500在qual_sorted中的位置:', next((i+1 for i,e in enumerate(qual_sorted) if e['code']=='562500'), 'NOT FOUND'))
print('515580在qual_sorted中的位置:', next((i+1 for i,e in enumerate(qual_sorted) if e['code']=='515580'), 'NOT FOUND'))
