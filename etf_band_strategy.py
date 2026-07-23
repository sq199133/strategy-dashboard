#!/usr/bin/env python3
"""
ETF波动性分析 & 波段策略回测系统
使用模拟数据展示框架（实际使用时网络恢复后可运行真实数据）
"""
import json
import random
import numpy as np
from datetime import datetime

# ============== 1. 加载 ETF 池 ==============
with open(r"D:\QClaw_Trading\data\etf_pool_V1_full.json", "r", encoding="utf-8") as f:
    pool = json.load(f)

etfs = pool['data']

# ============== 2. 模拟波动性数据 ==============
# 按类别模拟典型波动率（真实数据需要网络获取）
category_vol = {
    "科技/TMT/AI": (28, 45),      # 科技类波动最高
    "芯片半导体": (30, 50),
    "新能源": (25, 40),
    "商品/周期/资源": (22, 38),
    "医药生物": (18, 28),
    "科创板": (25, 42),
    "跨境QDII-海外": (20, 35),
    "港股/中概": (22, 36),
    "红利策略": (10, 18),
    "宽基A股": (15, 25),
    "金融": (16, 24),
    "消费": (14, 22),
    "制造/基建/公用": (12, 20),
    "其他": (15, 25)
}

results = []
for etf in etfs:
    cat = etf.get('category', '其他')
    vol_range = category_vol.get(cat, (15, 25))
    
    # 模拟年化波动率
    annual_vol = random.uniform(*vol_range)
    atr_pct = annual_vol * 0.35
    price_range = annual_vol * 2.5
    max_dd = -annual_vol * 1.2
    
    results.append({
        'code': etf['code'],
        'name': etf['name'],
        'category': cat,
        'annual_vol': round(annual_vol, 1),
        'atr_pct': round(atr_pct, 1),
        'price_range_250d': round(price_range, 1),
        'max_drawdown': round(max_dd, 1),
        'scale': etf.get('scale', 0)
    })

# 按波动率排序
results.sort(key=lambda x: x['annual_vol'], reverse=True)

# ============== 3. 高波动ETF Top 30 ==============
print("=" * 90)
print("ETF波动性分析 - Top 30 高波动ETF")
print("=" * 90)
print(f"{'代码':<8} {'名称':<20} {'类别':<12} {'年化波动':>8} {'ATR':>6} {'250日波动':>10} {'最大回撤':>10}")
print("-" * 90)

for i, r in enumerate(results[:30]):
    print(f"{r['code']:<8} {r['name'][:18]:<20} {r['category'][:10]:<12} {r['annual_vol']:>7.1f}% {r['atr_pct']:>5.1f}% {r['price_range_250d']:>9.1f}% {r['max_drawdown']:>9.1f}%")

# ============== 4. 波段策略定义 ==============
strategies = {
    "MA_cross": {
        "name": "均线交叉",
        "desc": "5日均线上穿20日买入，下穿卖出",
        "param": "short_ma=5, long_ma=20",
        "适合波动": "中低波动"
    },
    "Bollinger": {
        "name": "布林带突破",
        "desc": "突破上轨买入，跌破下轨卖出",
        "param": "window=20, std=2",
        "适合波动": "中波动"
    },
    "RSI": {
        "name": "RSI超买超卖",
        "desc": "RSI<30买入，RSI>70卖出",
        "param": "period=14, oversold=30, overbought=70",
        "适合波动": "任意"
    },
    "Breakout": {
        "name": "趋势突破",
        "desc": "20日高点突破买入，20日低点跌破卖出",
        "param": "lookback=20, atr_mult=2",
        "适合波动": "高波动"
    },
    "ATR_stop": {
        "name": "ATR止损",
        "desc": "突破买入后用2倍ATR设置止损",
        "param": "atr_mult=2",
        "适合波动": "高波动"
    }
}

print("\n" + "=" * 90)
print("可用波段策略")
print("=" * 90)
for k, v in strategies.items():
    print(f"{k}: {v['name']}")
    print(f"   说明: {v['desc']}")
    print(f"   参数: {v['param']}")
    print(f"   适合波动: {v['适合波动']}\n")

# ============== 5. 推荐匹配 ==============
print("=" * 90)
print("ETF与策略推荐匹配")
print("=" * 90)

# 高波动ETF推荐趋势突破策略
high_vol = [r for r in results[:15] if r['annual_vol'] > 30]
mid_vol = [r for r in results[15:50] if r['annual_vol'] > 20]

print("\n【高波动ETF ( >30% ) - 推荐趋势突破/Bollinger】")
for r in high_vol[:10]:
    print(f"  {r['code']} {r['name'][:15]} 波动:{r['annual_vol']:.1f}%")

print("\n【中高波动ETF (20-30%) - 推荐均线/RSI】")
for r in mid_vol[:10]:
    print(f"  {r['code']} {r['name'][:15]} 波动:{r['annual_vol']:.1f}%")

# 保存结果
output = {
    "analysis_date": datetime.now().strftime("%Y-%m-%d"),
    "total_etfs": len(results),
    "high_volatility_etfs": results[:50],
    "strategies": strategies
}

with open(r"D:\QClaw_Trading\data\etf_volatility_analysis.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n分析结果已保存到 etf_volatility_analysis.json")