import json

data_file = r'D:\QClaw_Trading\data\history_long_v2\562500.json'
with open(data_file, encoding='utf-8') as f:
    obj = json.load(f)
records = obj.get('records', [])
if 'records' in obj:
    records = obj['records']

print(f"总记录: {len(records)}")

wk = records[-20:]
closes = [r['close'] for r in wk]
dates = [r['date'] for r in wk]
vols = [r.get('vol', 0) for r in wk]

# MA3
ma3 = sum(closes[-3:]) / 3
# MA13
ma13 = sum(closes[-13:]) / 13
# MA21 (需要21条记录)
if len(records) >= 21:
    ma21_records = records[-21:]
    ma21 = sum(r['close'] for r in ma21_records) / 21
else:
    ma21 = sum(r['close'] for r in records) / len(records)

last_close = closes[-1]
dev = (last_close - ma13) / ma13 * 100
mom1w = closes[-1] / closes[-2] - 1
mom3w = closes[-1] / closes[-4] - 1

# 20周涨幅
if len(records) >= 21:
    mom20w = closes[-1] / records[-21]['close'] - 1
else:
    mom20w = None

print(f"\n=== 核心指标 ===")
print(f"MA3={ma3:.4f}, MA13={ma13:.4f}, MA21={ma21:.4f}")
print(f"偏离度: {dev:.2f}%")
print(f"MOM1W: {mom1w*100:.2f}%")
print(f"MOM3W: {mom3w*100:.2f}%")
print(f"20周涨幅: {mom20w*100:.2f}%" if mom20w else "20周涨幅: 数据不足")

# 趋势
print(f"\nMA3>MA13: {ma3>ma13}")
print(f"MA13>MA21: {ma13>ma21}")
print(f"均线多头: {ma3>ma13 and ma13>ma21}")

# 全部基础条件汇总
print(f"\n=== 基础持仓条件 ===")
print(f"偏离度<15%: {dev<15}  (实际{dev:.2f}%)")
print(f"MOM1W>=-1%: {mom1w>=-0.01}  (实际{mom1w*100:.2f}%)")
print(f"MOM3W>=0%: {mom3w>=0}  (实际{mom3w*100:.2f}%)")
print(f"均线多头: {ma3>ma13 and ma13>ma21}")

# B1红三兵
print(f"\n=== B1红三兵 ===")
bullish_3w = []
for i in range(-3, 0):
    b = wk[i]['close'] > wk[i]['open']
    print(f"  {wk[i]['date']}: close={wk[i]['close']} open={wk[i]['open']} 阳线={b}")
    bullish_3w.append(b)
print(f"连续3周阳线: {all(bullish_3w)}")
lows = [wk[-3]['low'], wk[-2]['low'], wk[-1]['low']]
print(f"近3周低点: {lows}")
print(f"低点逐周抬高: {lows[1]>lows[0] and lows[2]>lows[1]}")

# 量能
vol_ma13 = sum(vols[-13:]) / 13
vol_last = vols[-1]
vol_ratio = vol_last / vol_ma13
print(f"13周均量: {vol_ma13/1e9:.2f}B, 本周量: {vol_last/1e9:.2f}B, 量比: {vol_ratio:.2f}x")

# C仙人指路
print(f"\n=== C仙人指路 ===")
last_wk = wk[-1]
open_p = last_wk['open']
close_p = last_wk['close']
high_p = last_wk['high']
low_p = last_wk['low']
is_bullish = close_p > open_p
body = abs(close_p - open_p)
upper = high_p - close_p
lower = close_p - low_p
print(f"阳线: {is_bullish}")
print(f"上影线={upper:.4f}, 下影线={lower:.4f}, 实体={body:.4f}")
print(f"上影>实体: {upper > body}")
print(f"下影<0.5*实体: {lower < 0.5*body}")
print(f"量比>0.5x: {vol_ratio > 0.5}")
print(f"均线多头: {ma3>ma13 and ma13>ma21}")
print(f"20周涨幅<50%: {(mom20w*100<50) if mom20w else '数据不足'}")
c_pass = is_bullish and upper>body and lower<0.5*body and vol_ratio>0.5 and (ma3>ma13 and ma13>ma21) and (mom20w*100<50 if mom20w else False)
print(f"C仙人指路全部通过: {c_pass}")

# 核心结论
print(f"\n=== 落选原因分析 ===")
print(f"偏离度 {dev:.2f}% <= 15% ✓")
print(f"MOM3W {mom3w*100:.2f}% >= 0% ✓")
print(f"均线多头 ✓")
print(f"MOM1W {mom1w*100:.2f}% >= -1% ✓")
print(f"---")
print(f"B1红三兵: {all(bullish_3w) and lows[1]>lows[0] and lows[2]>lows[1]}")
print(f"C仙人指路: {c_pass}")
print(f"---")
print(f"562500 3周动量 {mom3w*100:.2f}% 本身很强，")
print(f"但B1/C型加分条件不满足（或者数据不足），")
print(f"最终要看扫描时TOP2的得分是否比它更高")
