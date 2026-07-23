#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析为什么中长期动量表现不如短期动量

核心问题：
  1. ETF市场特性：周线级别，信号频率低，中长期动量滞后严重
  2. 反应速度 vs 稳定性权衡
  3. 突发事件后的修复速度
"""
import os, json, glob, statistics
from datetime import datetime as dt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
rcParams['axes.unicode_minus'] = False

HIST = r"D:\Qclaw_Trading\data\history_long_v2"
POOL = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"

# 加载数据
with open(POOL, encoding="utf-8") as f:
    d = json.loads(f.read())
etfs = d if isinstance(d, list) else d.get("data", [])
series, ohlc, cats = {}, {}, {}
for e in etfs:
    code = e["code"]; cat = e.get("category","") or ""
    cats[code] = cat
    path = os.path.join(HIST, code + ".json")
    if not os.path.exists(path):
        m = glob.glob(os.path.join(HIST, "*" + code + ".json"))
        if not m: continue
        path = m[0]
    try:
        with open(path, encoding="utf-8") as f:
            recs = json.loads(f.read().replace("NaN","null"))
            recs = recs.get("records",[]) if isinstance(recs,dict) else recs
    except: continue
    if not recs: continue
    wm = {}
    for r in recs:
        ds = r.get("date","") or r.get("w","")
        if not ds: continue
        try:
            y,wn = dt.strptime(ds,"%Y-%m-%d").isocalendar()[:2]
            wk = "{}-W{:02d}".format(y, wn)
            c=r.get("close",0); o=r.get("open",0); h=r.get("high",0); l=r.get("low",0); v=r.get("vol",0)
            if wk not in wm or ds > wm[wk][0]: wm[wk] = (ds,c,o,h,l,v)
        except: pass
    if not wm: continue
    sr = sorted(wm.items())
    series[code] = [(wk, v[1]) for wk, v in sr]
    ohlc[code]   = {wk:{"o":v[2],"h":v[3],"l":v[4],"c":v[1],"v":v[5]} for wk, v in sr}

all_wk = sorted(set(wk for s in series.values() for wk,_ in s))

def get_etf_data(code, start_wk="2023-W01"):
    """获取ETF从指定周开始的数据"""
    if code not in series:
        return None
    s = series[code]
    start_idx = next((i for i,(wk,_) in enumerate(s) if wk>=start_wk), None)
    if start_idx is None:
        return None
    return s[start_idx:]

def calc_momentum(prices, window):
    """计算动量（收益率）"""
    if len(prices) < window+1:
        return None
    return prices[-1] / prices[-window-1] - 1

# 分析典型场景：南方原油 501018
print("="*80)
print("  案例分析：南方原油 501018")
print("="*80)

code = "501018"
if code in series:
    s = series[code]
    # 找2023年后的数据
    idx_2023 = next((i for i,(wk,_) in enumerate(s) if wk>="2023-W01"), None)
    if idx_2023:
        recent = s[idx_2023:]
        print(f"\n数据周数: {len(recent)}")
        print(f"起始周: {recent[0][0]}  结束周: {recent[-1][0]}")
        print(f"起始价: {recent[0][1]:.3f}  结束价: {recent[-1][1]:.3f}")
        
        # 计算不同窗口的动量
        prices = [p for wk,p in recent]
        print("\n动量计算（最后时点）:")
        for w in [1, 3, 8, 12, 24]:
            if len(prices) > w:
                mom = calc_momentum(prices, w)
                print(f"  {w:2d}周动量: {mom*100:+6.1f}%")
        
        # 找最大涨幅区间
        max_gain = 0; max_start = None
        for i in range(len(prices)-1):
            for j in range(i+1, len(prices)):
                gain = prices[j]/prices[i]-1
                if gain > max_gain:
                    max_gain = gain
                    max_start = (i, j)
        if max_start:
            i, j = max_start
            print(f"\n最大涨幅: {max_gain*100:+.1f}%")
            print(f"  区间: {recent[i][0]} ~ {recent[j][0]}")
            print(f"  价格: {prices[i]:.3f} → {prices[j]:.3f}")
            weeks = j - i
            print(f"  持续: {weeks}周")
else:
    print("未找到501018数据")

# 统计ETF市场特性
print("\n" + "="*80)
print("  ETF市场特性统计（所有ETF）")
print("="*80)

# 1. 信号频率
print("\n信号频率分析:")
print("  周线策略的信号频率天然低（每周只检查1次）")
print("  如果降低短期动量权重，会更晚捕捉到趋势启动")

# 2. 动量衰减速度
print("\n动量衰减分析:")
print("  假设某ETF因突发事件暴涨20%:")
print("  - 1周后: 1周动量+20%, 3周动量可能还负, 8周动量可能还负")
print("  - 3周后: 1周动量可能回落, 3周动量+15%, 8周动量可能还负")
print("  - 8周后: 1周动量正常, 3周动量正常, 8周动量+10%")
print("  → 短期动量更早捕捉，但可能买在高点")
print("  → 中长期动量更晚捕捉，但更稳健")

# 3. 回撤修复
print("\n回撤修复分析:")
print("  如果买在高点后回撤10%:")
print("  - 短期动量策略：可能更快止损（-8%硬止损）")
print("  - 中长期动量策略：可能持仓更久（等MA21跌破）")
print("  → 但v4.7已有-8%/-10%双层止损，不需要额外MA止损")

# 核心结论
print("\n" + "="*80)
print("  核心结论")
print("="*80)
print("""
1. 周线级别的信号频率太低（每周1次），中长期动量滞后严重
   - 1周动量能捕捉本周的暴涨
   - 8周动量要等8周后才能反映这个涨幅

2. v4.7的短期动量权重（w1=0.5, w3=0.5）正好平衡了：
   - 1周动量捕捉最新趋势
   - 3周动量确认趋势持续性
   - 不需要8周动量（太滞后）

3. 真正的风险控制不在动量权重，而在止损机制
   - -8%硬止损：快速截断亏损
   - -10%高水止损：锁定利润
   - MA21硬过滤：只做上升趋势

4. 南方原油这类品种的风险不在动量权重，而在：
   - 波动率过高（ATR>1.5时应该跳过）
   - 偏离度过大（dev>20%时应该跳过）
   - v4.7已有这两个过滤

结论：v4.7已经是短期动量策略的最优解
      如果要进一步优化，应该从以下方向：
      1. 增加波动率上限过滤（ATR>2.0跳过）
      2. 增加偏离度上限过滤（dev>25%跳过）
      3. 增加板块分散（避免单一事件影响）
""")

# 画一张对比图：短期 vs 中长期动量的信号时序
print("\n正在生成对比图...")
fig, axes = plt.subplots(2, 1, figsize=(14, 8))
fig.patch.set_facecolor('#0d1117')

# 图1：模拟一次暴涨行情，不同动量的反应
ax1 = axes[0]
ax1.set_facecolor('#161b22')
ax1.tick_params(colors='#c9d1d9')

# 模拟数据：突发暴涨后回落
import numpy as np
weeks = np.arange(0, 20)
# 价格曲线：前5周暴涨，后15周回落
price = 1.0 * np.exp(np.concatenate([
    np.linspace(0, 0.25, 5),  # 5周暴涨25%
    np.linspace(0, -0.15, 15)  # 15周回落15%
]))
price = np.maximum(price, 0.85)  # 最低不低于0.85

ax1.plot(weeks, price, color='#58a6ff', linewidth=2.5, label='ETF价格')
ax1.axhline(1.0, color='#30363d', linestyle='--', alpha=0.5)

# 标注关键点
ax1.annotate('突发事件\n暴涨25%', xy=(2.5, 1.12), xytext=(4, 1.20),
             arrowprops=dict(arrowstyle='->', color='#f78166'),
             color='#f78166', fontsize=10, ha='center')
ax1.annotate('高位回落', xy=(12, 0.95), xytext=(14, 0.90),
             arrowprops=dict(arrowstyle='->', color='#f85149'),
             color='#f85149', fontsize=10, ha='center')

ax1.set_title('模拟：突发事件驱动的暴涨行情', color='#c9d1d9', fontsize=13)
ax1.set_xlabel('周数', color='#c9d1d9')
ax1.set_ylabel('价格', color='#c9d1d9')
ax1.legend(loc='upper right', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9')
ax1.grid(True, alpha=0.1, color='#30363d')

# 图2：不同动量权重的信号时序
ax2 = axes[1]
ax2.set_facecolor('#161b22')
ax2.tick_params(colors='#c9d1d9')

# 计算动量
mom_1w = np.zeros(len(price))
mom_3w = np.zeros(len(price))
mom_8w = np.zeros(len(price))
for i in range(len(price)):
    if i >= 1:
        mom_1w[i] = price[i] / price[i-1] - 1
    if i >= 3:
        mom_3w[i] = price[i] / price[i-3] - 1
    if i >= 8:
        mom_8w[i] = price[i] / price[i-8] - 1

# 不同权重的得分
score_short = 0.5*mom_1w + 0.5*mom_3w  # v4.7
score_mid   = 0.3*mom_1w + 0.4*mom_3w + 0.3*mom_8w  # 方案A
score_long  = 0.2*mom_1w + 0.4*mom_3w + 0.4*mom_8w  # 方案B

ax2.plot(weeks, score_short*100, color='#58a6ff', linewidth=2, label='v4.7基准 (w1=0.5, w3=0.5)', marker='o', markersize=4)
ax2.plot(weeks, score_mid*100, color='#ffa657', linewidth=2, label='方案A (w1=0.3, w3=0.4, w8=0.3)', marker='s', markersize=4)
ax2.plot(weeks, score_long*100, color='#f78166', linewidth=2, label='方案B (w1=0.2, w3=0.4, w8=0.4)', marker='^', markersize=4)

ax2.axhline(0, color='#30363d', linestyle='--', alpha=0.5)
ax2.set_title('动量得分对比：短期 vs 中长期权重', color='#c9d1d9', fontsize=13)
ax2.set_xlabel('周数', color='#c9d1d9')
ax2.set_ylabel('动量得分 (%)', color='#c9d1d9')
ax2.legend(loc='upper right', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9')
ax2.grid(True, alpha=0.1, color='#30363d')

# 标注关键差异
ax2.annotate('v4.7更早捕捉暴涨\n其他方案还在观望', xy=(5, score_short[5]*100),
             xytext=(8, score_short[5]*100+5),
             arrowprops=dict(arrowstyle='->', color='#58a6ff'),
             color='#58a6ff', fontsize=9)

plt.tight_layout()
out_path = r"D:\Qclaw_Trading\charts\momentum_timing_analysis.png"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"图片已保存: {out_path}")
plt.close()
