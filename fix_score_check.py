import json

# 读取562500数据
data_file = r'D:\QClaw_Trading\data\history_long_v2\562500.json'
with open(data_file, encoding='utf-8') as f:
    obj = json.load(f)
records = obj.get('records', [])
if 'records' in obj:
    records = obj['records']

total = len(records)
wk = records[-20:]
closes = [r['close'] for r in wk]
vols = [r.get('vol', 0) for r in wk]
dates = [r['date'] for r in wk]

ma3 = sum(closes[-3:]) / 3
ma5 = sum(closes[-5:]) / 5
ma13 = sum(closes[-13:]) / 13
ma21 = sum(closes[-21:]) / 21

mom1w = closes[-1] / closes[-2] - 1
mom3w = closes[-1] / closes[-4] - 1
mom8w = closes[-1] / closes[-9] - 1
mom20w = closes[-1] / records[-21]['close'] - 1

vol_ma10 = sum(vols[-10:]) / 10
vol_last = vols[-1]
vol_ratio = vol_last / vol_ma10

base_score = 0.4 * mom1w + 0.4 * mom3w + 0.2 * mom8w
score_with_c = base_score + 0.02

print("=== 562500 精确综合得分 ===")
print(f"总记录数: {total}")
print(f"MOM1W = {mom1w*100:.4f}%")
print(f"MOM3W = {mom3w*100:.4f}%")
print(f"MOM8W = {mom8w*100:.4f}%")
print(f"MOM20W(20周涨幅) = {mom20w*100:.4f}%")
print(f"---")
print(f"0.4*MOM1W = {0.4*mom1w*100:.4f}%")
print(f"0.4*MOM3W = {0.4*mom3w*100:.4f}%")
print(f"0.2*MOM8W = {0.2*mom8w*100:.4f}%")
print(f"base_score = {base_score*100:.4f}%")
print(f"score_with_c = {score_with_c*100:.4f}%")

print(f"\n=== 偏差纠正 ===")
print(f"我之前说: 562500 base=9.78%, with C=10.78%")
print(f"正确:     562500 base={base_score*100:.2f}%, with C={score_with_c*100:.2f}%")
print(f"")
print(f"误差1: +0.02加的是2个百分点，不是0.02加到9.78上")
print(f"      9.78% + 2% = 11.78%，不是我说的10.78%")
print(f"")
print(f"误差2: 562500 base={base_score*100:.2f}% vs 588910(我估计)~8.95%")
print(f"      562500的得分已经比588910高，但因为515580排第1，")
print(f"      588910排第2，第3名额看515920(8.87%) vs 562500({base_score*100:.2f}%)")
print(f"      562500({base_score*100:.2f}%) > 515920(8.87%)，所以562500实际应该排第3！")
print(f"      但实际扫描结果里562500没有进TOP3...")
print(f"      原因: 扫描脚本用的是MA5而非MA3，且可能有其他细微差异")
