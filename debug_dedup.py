import json

with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260704_164149.json', encoding='utf-8') as f:
    data = json.load(f)

all_etfs = data['all']

# 扫描脚本里qual的顺序 = 遍历all的顺序（按代码遍历）
qual = [e for e in all_etfs if e['passed']]
print(f'qual列表前10个（扫描遍历顺序）:')
for e in qual[:10]:
    print(f'  {e["code"]} {e["name"]} 赛道={e["cat"]} 得分={e["score"]*100:.2f}%')

print()
print('=== 用扫描脚本的实际qual顺序做dedup ===')
cats = set()
dedup_actual = []
for e in qual:  # 按扫描遍历顺序，不是按得分排序
    c = e['cat'] or e['code']
    if c not in cats:
        cats.add(c)
        dedup_actual.append(e)

print('dedup后的完整列表（8只）:')
for i, e in enumerate(dedup_actual):
    print(f'  {i+1}. {e["code"]} {e["name"]} 赛道={e["cat"]} 得分={e["score"]*100:.2f}%')

print()
print(f'top3: {[e["code"] for e in dedup_actual[:3]]}')
print()
print('=== 问题所在 ===')
print('扫描脚本的qual顺序是按代码遍历的，不是按得分排序')
print('所以562500（代码5开头）排在515580（代码5开头，但数值更大）之前')
print('但扫描脚本的TARGET是去重后的前3名，所以562500才应该排第1')
print()
print('然而实际扫描结果TOP3是: 515580, 588910, 515920')
print('这说明...扫描脚本里qual列表的顺序不是代码顺序')
print('让我直接从JSON的target字段和all字段里核实')

# 从all里找515580和562500的顺序
print()
print('515580在all中的索引:', next((i for i,e in enumerate(all_etfs) if e['code']=='515580'), None))
print('562500在all中的索引:', next((i for i,e in enumerate(all_etfs) if e['code']=='562500'), None))
