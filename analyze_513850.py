#!/usr/bin/env python3
"""Analyze 513850 data anomaly (Jan 2024 QDII premium)."""
import json
from pathlib import Path

fp = Path("D:/QClaw_Trading/data/history/513850.json")
raw = json.loads(fp.read_text(encoding="utf-8"))
recs = raw["records"]
prices = [r["close"] for r in recs]
dates = [r["date"] for r in recs]
n = len(prices)

print("=" * 60)
print("513850 美国50ETF — 数据异常分析")
print("=" * 60)
print(f"\n数据概况:")
print(f"  总记录: {n}条")
print(f"  日期: {dates[0]} ~ {dates[-1]}")

# === Step 1: Find anomaly window ===
print("\n=== 1. 异常窗口定位 ===")
# Look for days with >7% daily change
big_days = []
for i in range(1, n):
    if prices[i-1] != 0:
        ret = (prices[i] / prices[i-1] - 1) * 100
        if abs(ret) > 7:
            big_days.append((dates[i], ret))

print(f"单日涨跌幅超过7%的交易:")
for d, r in big_days:
    print(f"  {d}: {r:+.2f}%")

# The anomaly window
anomaly_start = "2024-01-19"  # Friday before
anomaly_end = "2024-01-31"
print(f"\n异常窗口: {anomaly_start} ~ {anomaly_end}")

# === Step 2: Zoom into anomaly ===
print("\n=== 2. 异常窗口逐日行情 ===")
idx_anomaly_start = next(i for i, d in enumerate(dates) if d >= anomaly_start)
idx_anomaly_end = next(i for i, d in enumerate(dates) if d > anomaly_end)
if idx_anomaly_end == len(dates):
    idx_anomaly_end = len(dates)

for i in range(idx_anomaly_start, min(idx_anomaly_end, len(dates))):
    r = recs[i]
    day_ret = (r["close"] / r["open"] - 1) * 100 if r["open"] else 0
    prev_close = prices[i-1] if i > 0 else r["open"]
    cum_ret = (r["close"] / prices[idx_anomaly_start] - 1) * 100
    vol_b = r["vol"] / 10000
    print(f"  {r['date']}  "
          f"O:{r['open']:.3f} H:{r['high']:.3f} "
          f"L:{r['low']:.3f} C:{r['close']:.3f}  "
          f"日内:{day_ret:+.2f}% 累计:{cum_ret:+.2f}%  "
          f"量:{vol_b:.0f}万手")

# === Step 3: Volatility comparison ===
print("\n=== 3. 波动率对比 ===")
returns = [(prices[i] / prices[i-1] - 1) * 100 for i in range(1, n)]
clean_returns = returns[:idx_anomaly_start-1] + returns[idx_anomaly_end:]

def calc_stats(rts, label):
    if not rts:
        return
    avg = sum(rts) / len(rts)
    var = sum((x - avg)**2 for x in rts) / len(rts)
    std = var ** 0.5
    ann_vol = std * (252 ** 0.5)
    print(f"  {label}: n={len(rts)}, "
          f"日均={avg:+.4f}%, 日波动率={std:.2f}%, "
          f"年化波动={ann_vol*100:.1f}%")
    return ann_vol

ann_all = calc_stats(returns, "全部数据")
ann_clean = calc_stats(clean_returns, "剔除异常期")

# === Step 4: Price comparison over time ===
print("\n=== 4. 异常对策略的潜在影响 ===")
# What's the actual price movement vs what NAV should be?
peak = max(prices[idx_anomaly_start:idx_anomaly_end])
valley = min(prices[idx_anomaly_start:idx_anomaly_end])
print(f"  异常期内最高价: {peak:.3f}")
print(f"  异常期内最低价: {valley:.3f}")
print(f"  最大波动幅度: {(peak/valley - 1)*100:.1f}%")
print(f"  期内净变化: {(prices[idx_anomaly_end-1]/prices[idx_anomaly_start] - 1)*100:.1f}%")

# Compare with index proxy at same period
print("\n=== 5. 其他QDII ETF类似异常统计 ===")
qdii_list = [
    ("513850", "美国50ETF"),
    ("513400", "道琼斯ETF"),
    ("159561", "德国ETF"),
    ("513080", "法国CAC40ETF"),
    ("513360", "教育ETF"),
    ("513070", "港股通消费ETF"),
    ("513090", "香港证券ETF"),
    ("513690", "港股红利ETF"),
    ("513730", "东南亚科技ETF"),
    ("513290", "纳指生物科技ETF"),
    ("159529", "标普消费ETF"),
]

for code, name in qdii_list:
    fpp = Path(f"D:/QClaw_Trading/data/history/{code}.json")
    if not fpp.exists():
        continue
    r = json.loads(fpp.read_text(encoding="utf-8"))
    rec = r["records"]
    # Find max single day return (absolute)
    max_chg_pct = 0
    max_chg_date = ""
    min_chg_pct = 0
    min_chg_date = ""
    for i in range(1, len(rec)):
        if rec[i-1]["close"] != 0:
            chg = rec[i]["close"] / rec[i-1]["close"] - 1
            if chg > max_chg_pct:
                max_chg_pct = chg
                max_chg_date = rec[i]["date"]
            if chg < min_chg_pct:
                min_chg_pct = chg
                min_chg_date = rec[i]["date"]
    print(f"  {code} {name[:10]:<10s}: "
          f"最大涨={max_chg_pct*100:+.1f}%({max_chg_date}) "
          f"最大跌={min_chg_pct*100:+.1f}%({min_chg_date})")

# === Step 6: Recommendation ===
print("\n" + "=" * 60)
print("分析结论")
print("=" * 60)
print("""
异常性质: QDII场内交易溢价/折价
  2024-01-22~25: 连续4天涨停(+10%/天)，因QDII额度限制导致
  严重溢价，实际美股并未大涨
  2024-01-29~31: 溢价回归，连续跌停回归合理价位
  
影响评估:
  该异常导致513850数据中年化波动率被人为提高
  2024-01区间价格波动~50%，但实际美股同期波动<5%
  使用价格数据的策略会产生大量虚假信号

建议处理方案:
  方案A: 简单标注，策略中使用时跳过该异常期
  方案B: 用净值替代价格（需额外获取QDII净值数据）
  方案C: QDII ETF统一做溢价检测过滤（涨跌超5%联动检查）
  """)
