"""
四方达 卖出策略分析
"""
import pandas as pd, numpy as np

d = pd.read_csv(r"D:\QClaw_Trading\data\300179_四方达.csv", encoding="utf-8-sig")
for c in ["close","high","low","volume"]:
    d[c] = pd.to_numeric(d[c], errors="coerce")

# ATR
tr = pd.concat([
    d["high"] - d["low"],
    (d["high"] - d["close"].shift()).abs(),
    (d["low"] - d["close"].shift()).abs()
], axis=1).max(axis=1)
d["atr14"] = tr.rolling(14).mean()

# 10日低
d["ch10l"] = d["low"].rolling(10).min()

# RSI
delta = d["close"].diff()
g = delta.where(delta > 0, 0).rolling(14).mean()
l = (-delta.where(delta < 0, 0)).rolling(14).mean()
d["rsi"] = 100 - 100 / (1 + g / l.replace(0, np.nan))

last = d.iloc[-1]
atr = last["atr14"]
entry = 57.48

print("=" * 55)
print("  四方达(300179) 卖出规则手册  |  Turtle_20x10_DoubleLoss")
print("=" * 55)

print(f"\n1. ATR双重损失止损 (硬止损)")
print(f"   {'.'*35}")
print(f"   ATR(14) = {atr:.2f}")
init_stop = entry - 0.5 * atr
print(f"   init_stop = {entry} - 0.5*{atr:.2f} = {init_stop:.2f}")
print(f"   max_loss = {(init_stop/entry - 1)*100:.1f}%")
print(f"   >> 价格跌破 {init_stop:.2f} -> 无条件离场")

print(f"\n2. 唐奇安通道出场 (10日低点)")
print(f"   {'.'*35}")
ch10l = last["ch10l"]
print(f"   最新10日最低价 = {ch10l:.2f}")
print(f"   当前收盘价 = {last['close']:.2f}")
print(f"   距10日底距离 = {last['close']-ch10l:.2f} ({(last['close']/ch10l-1)*100:.1f}%)")
print(f"   >> 收盘跌破 {ch10l:.2f} -> 趋势反转, 离场")

print(f"\n3. 峰值追踪止盈 (浮动)")
print(f"   {'.'*35}")
peak = d["close"].rolling(20).max().iloc[-1]
trail_stop = peak - 0.5 * atr
print(f"   近20日峰值 = {peak:.2f}")
trail_buf = 0.5 * atr
print(f"   追踪缓冲 = 0.5 * {atr:.2f} = {trail_buf:.2f}")
print(f"   当前追踪止损 = {trail_stop:.2f}")
print(f"   >> 价格每创新高, 止损同步上移")
print(f"   >> 若跌回追踪止损线 -> 锁定利润离场")

print(f"\n4. 顺势卖出信号")
print(f"   {'.'*35}")
print(f"   - MA死叉: MA5跌破MA20")
print(f"   - MACD顶背离: 价格新高但MACD未同创新高")
print(f"   - 天量滞涨: 成交量放巨量但价格不涨")

print(f"\n5. 当前关键位")
print(f"   {'.'*35}")
ma20 = d["close"].rolling(20).mean().iloc[-1]
ma60 = d["close"].rolling(60).mean().iloc[-1]
bb_mid = d["close"].rolling(20).mean().iloc[-1]
bb_std = d["close"].rolling(20).std().iloc[-1]
bb_u = bb_mid + 2 * bb_std
print(f"   MA20 = {ma20:.2f}")
print(f"   MA60 = {ma60:.2f}")
print(f"   布林上轨 = {bb_u:.2f}")
print(f"   RSI(14) = {last['rsi']:.1f}")
print(f"   现价 = {last['close']:.2f}")

print(f"\n{'='*55}")
print(f"  仓位管理")
print(f"{'='*55}")
print(f"   入场仓位: 6.4%  (组合上限10%)")
print(f"   初始止损: {init_stop:.2f}  (-4.3%)")
print(f"   若浮盈+5% 加仓至 8%")
print(f"   若浮盈+10% 加仓至 10% (上限)")
print(f"   总敞口: 组合中最多3只同位, 总仓60%")

print(f"\n{'='*55}")
print(f"  一句话总结")
print(f"{'='*55}")
print(f"  入场: 已发生 (Turtle突破{entry})")
print(f"  持仓信号: 站稳MA20且维持10日低点以上")
print(f"  出场规则: 先到先触发 —")
print(f"   (A) 跌至{init_stop:.2f} 止损  |  (B) 收盘破{ch10l:.2f} 趋势离场  |  (C) 追踪止损上移后触发止盈")
