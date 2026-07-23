import json

data_file = r'D:\QClaw_Trading\data\history_long_v2\562500.json'
with open(data_file, encoding='utf-8') as f:
    obj = json.load(f)
records = obj.get('records', [])
if isinstance(records, list) and len(records) > 0 and isinstance(records[0], dict) and 'w' in records[0]:
    records = records  # dict wrap format
else:
    records = records

# 如果是dict包装格式
if 'records' in obj:
    records = obj['records']

print(f"总记录: {len(records)}")
print(f"最新数据日期: {records[-1]['date']}")

# 提取最近20条
wk = records[-20:]
closes = [r['close'] for r in wk]
dates = [r['date'] for r in wk]
vols = [r.get('vol', 0) for r in wk]

print("\n=== 核心指标计算 ===")

# MA3 = 近3周收盘均
ma3 = sum(closes[-3:]) / 3
print(f"MA3 (近3周均): {ma3:.4f}")

# MA13 = 近13周收盘均
ma13 = sum(closes[-13:]) / 13
print(f"MA13 (近13周均): {ma13:.4f}")

# MA21 = 近21周收盘均
ma21 = sum(closes[-21:]) / 21
print(f"MA21 (近21周均): {ma21:.4f}")

# 最新收盘
last_close = closes[-1]
print(f"最新收盘: {last_close}")

# 偏离度 = (close - MA13) / MA13
dev = (last_close - ma13) / ma13 * 100
print(f"偏离度 = (最新收盘 - MA13) / MA13: {dev:.2f}%")

# 1周动量 = 本周/上周 - 1
mom1w = closes[-1] / closes[-2] - 1
print(f"MOM1W (1周动量): {mom1w*100:.2f}%")

# 3周动量 = 本周/3周前 - 1
mom3w = closes[-1] / closes[-4] - 1
print(f"MOM3W (3周动量): {mom3w*100:.2f}%")

# 8周动量 = 本周/8周前 - 1
mom8w = closes[-1] / closes[-9] - 1
print(f"MOM8W (8周动量): {mom8w*100:.2f}%")

# 20周涨幅 = 本周/20周前 - 1
mom20w = closes[-1] / closes[-21] - 1
print(f"20周涨幅: {mom20w*100:.2f}%")

print("\n=== 趋势判断 ===")
# 均线多头
ma3_above_ma13 = ma3 > ma13
ma13_above_ma21 = ma13 > ma21
print(f"MA3 > MA13: {ma3_above_ma13}")
print(f"MA13 > MA21: {ma13_above_ma21}")
print(f"均线多头排列: {ma3_above_ma13 and ma13_above_ma21}")

# 偏离度 <= 15%
print(f"偏离度 <= 15%: {dev <= 15}")

# MOM1W >= -1%
print(f"MOM1W >= -1%: {mom1w*100 >= -1}")

# MOM3W >= 0%
print(f"MOM3W >= 0%: {mom3w >= 0}")

print("\n=== B1 红三兵检查 ===")
# 近3周阳线（close > open）
for i in range(-3, 0):
    is_bullish = wk[i]['close'] > wk[i]['open']
    print(f"  {wk[i]['date']}: close={wk[i]['close']} open={wk[i]['open']} 阳线={is_bullish}")

# 低点是否抬高
c1, c2, c3 = closes[-3], closes[-2], closes[-1]
low1 = min(r['low'] for r in wk[-3:])
low2 = min(r['low'] for r in wk[-2:])
low3 = min(r['low'] for r in wk[-1:])
print(f"\n近3周低点: {low1:.4f}, {low2:.4f}, {low3:.4f}")
print(f"低点抬高: {low2 > low1 and low3 > low2}")

# 量能检查：近3周量能稳定
vol_ma = sum(vols[-13:]) / 13  # 13周量能均量
vol_now = vols[-1]
print(f"\n近13周均量: {vol_ma/1e9:.2f}B")
print(f"本周量: {vol_now/1e9:.2f}B")
print(f"量比: {vol_now/vol_ma:.2f}x")

print("\n=== C仙人指路检查 ===")
last_wk = wk[-1]
prev_wk = wk[-2]
open_price = last_wk['open']
close_price = last_wk['close']
high_price = last_wk['high']
low_price = last_wk['low']

is_bullish_bar = close_price > open_price
upper_shadow = high_price - close_price
lower_shadow = close_price - low_price
body = abs(close_price - open_price)

print(f"阳线: {is_bullish_bar}")
print(f"上影线: {upper_shadow:.4f}")
print(f"下影线: {lower_shadow:.4f}")
print(f"实体: {body:.4f}")
print(f"上影线 > 实体: {upper_shadow > body}")
print(f"下影线 < 0.5*实体: {lower_shadow < 0.5 * body}")
print(f"量比: {vol_now/vol_ma:.2f}x")
print(f"均线多头: {ma3_above_ma13 and ma13_above_ma21}")
print(f"20周涨幅 < 50%: {mom20w*100 < 50}")
c_conditions = [
    is_bullish_bar,
    upper_shadow > body,
    lower_shadow < 0.5 * body,
    vol_now / vol_ma > 0.5,
    ma3_above_ma13 and ma13_above_ma21,
    mom20w * 100 < 50
]
print(f"C仙人指路全部满足: {all(c_conditions)}")
for idx, (cond, desc) in enumerate(zip(c_conditions, ['阳线', '上影>实体', '下影<0.5实体', '温和量', '均线多头', '20周<50%'])):
    print(f"  {desc}: {cond}")

print("\n=== 562500的3周动量排名预估 ===")
print(f"562500 3周动量: {mom3w*100:.2f}%")
print(f"策略要求LB=3,偏离度<=15%,趋势完好,MOM>=0")
print(f"562500 偏离度: {dev:.2f}% (需<=15%)")
print(f"562500 均线多头: {ma3_above_ma13 and ma13_above_ma21}")
print(f"562500 MOM3W>=0: {mom3w>=0}")
