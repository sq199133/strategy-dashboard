"""
今日完整分析: 13只股票 × 策略分配器
"""
import sys, os, json
sys.path.insert(0, r"D:\QClaw_Trading\backtest")
from strategy_allocator import (
    load_stock_data, compute_profile_indicators, profile_stock,
    check_entry, STOCK_NAMES, STRATEGY_KNOWLEDGE_BASE
)
import pandas as pd
import numpy as np
from datetime import date

def compute_v2_indicators(d):
    """完整回测级指标"""
    # MAs
    for p in [5,10,20,30,60,120]:
        d[f"ma{p}"] = d["close"].rolling(p).mean()
    # MACD
    e12 = d["close"].ewm(span=12, adjust=False).mean()
    e26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = e12 - e26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]
    # RSI 14
    delta = d["close"].diff()
    g = delta.where(delta > 0, 0).rolling(14).mean()
    l = (-delta.where(delta < 0, 0)).rolling(14).mean()
    d["rsi_14"] = 100 - (100 / (1 + g / l.replace(0, np.nan)))
    # ATR
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift()).abs(),
        (d["low"] - d["close"].shift()).abs()
    ], axis=1).max(axis=1)
    d["atr_14"] = tr.rolling(14).mean()
    # Volume
    d["vol_ma20"] = d["volume"].rolling(20).mean()
    d["vol_ratio"] = d["volume"] / d["vol_ma20"].replace(0, np.nan)
    d["cpct"] = d["close"].pct_change()
    # Channel
    d["ch20h"] = d["high"].rolling(20).max()
    d["ch20l"] = d["low"].rolling(20).min()
    d["ch10l"] = d["low"].rolling(10).min()
    # Bollinger
    d["bb_mid"] = d["ma20"]
    d["bb_std"] = d["close"].rolling(20).std()
    d["bb_upper"] = d["bb_mid"] + 2 * d["bb_std"]
    d["bb_lower"] = d["bb_mid"] - 2 * d["bb_std"]
    # AR人氣
    d["ar"] = ((d["high"] - d["open"]).rolling(26).sum() /
               (d["open"] - d["low"]).rolling(26).sum().replace(0, np.nan)) * 100
    d["pct"] = d["close"].pct_change()
    return d

def full_analysis(code, name):
    df = load_stock_data(code)
    d = compute_v2_indicators(df)
    p = profile_stock(code, df, d)
    
    last = d.iloc[-1]
    prev = d.iloc[-2]
    kb = STRATEGY_KNOWLEDGE_BASE.get(code, {})
    
    # Compute entry signal for primary strategy
    signal = check_entry(code, p, d)
    
    # Additional metrics
    vol = d["cpct"].std() * np.sqrt(252) * 100
    ma_align = sum([
        1 if last["ma5"] > last["ma10"] else -1,
        1 if last["ma10"] > last["ma20"] else -1,
        1 if last["ma20"] > last["ma60"] else -1,
    ])
    trend_dir = "多头" if ma_align > 1 else ("空头" if ma_align < -1 else "震荡")
    
    # Price position
    from_ch20l_pct = (last["close"] - last["ch20l"]) / (last["ch20h"] - last["ch20l"]) * 100 if last["ch20h"] > last["ch20l"] else 50
    bb_pos = "上轨" if last["close"] >= last["bb_upper"] else ("下轨" if last["close"] <= last["bb_lower"] else "中轨附近")
    
    rsi_now = last["rsi_14"]
    
    # 1Y return
    yr = (last["close"] / d["close"].iloc[-250] - 1) * 100 if len(d) >= 250 else 0
    
    return {
        "code": code,
        "name": name,
        "price": last["close"],
        "volatility": vol,
        "trend": trend_dir,
        "ma_align": ma_align,
        "rsi": rsi_now,
        "bb_pos": bb_pos,
        "pos_in_channel": from_ch20l_pct,
        "mkt_cap": last["amount"] * 250 / 1e8 if "amount" in last else 0,
        "return_1y": yr,
        "primary_strategy": kb.get("primary", "?"),
        "alt_strategy": kb.get("alternative", "?"),
        "personality": kb.get("personality", "?"),
        "entry_signal": signal["signal"] if signal else "无",
        "entry_reason": signal["reason"] if signal else "—",
        "stop_price": signal["stop_price"] if signal else "—",
        "stop_pct": signal["stop_loss_pct"] if signal else "—",
        "pos_pct": signal["position_pct"] if signal else 0,
        "latest_date": str(last.name) if hasattr(last, 'name') else d["date"].iloc[-1],
    }

# ── Run ──
codes = sorted(STOCK_NAMES.keys())
results = []

for code in codes:
    name = STOCK_NAMES[code]
    r = full_analysis(code, name)
    results.append(r)

# ── Print ──
print("=" * 90)
print(f"  个股量化全景扫描  |  {date.today().isoformat()}")
print("  Baostock 数据  |  信号引擎: 海龟/MA倾向/RSI反转/量价突破/组合")
print("=" * 90)
print()

for r in results:
    sig_mark = "[BUY]" if r["entry_signal"] == "BUY" else "[---]"
    print(f"  {sig_mark} {r['code']} {r['name']}")
    print(f"    ├─ 现价: {r['price']:.2f}  |  年化波动: {r['volatility']:.1f}%  |  1Y涨跌: {r['return_1y']:+.1f}%")
    print(f"    ├─ 趋势: {r['trend']}  |  MA排列: {r['ma_align']}  |  RSI: {r['rsi']:.1f}")
    print(f"    ├─ 通道内位置: {r['pos_in_channel']:.0f}%  |  布林带: {r['bb_pos']}")
    print(f"    ├─ 画像: {r['personality']}")
    print(f"    ├─ 主策略: {r['primary_strategy']}")
    if r["entry_signal"] == "BUY":
        print(f"    └─ [BUY] {r['entry_reason']}")
        print(f"      止损: {r['stop_price']:.2f} ({r['stop_pct']:+.1f}%)  |  仓位: {r['pos_pct']:.1f}%")
    else:
        print(f"    └─ 无入场信号")
    print()

# ── Summary ──
print("─" * 90)
signals = [r for r in results if r["entry_signal"] == "BUY"]
if signals:
    print(f"[BUY] 信号汇总: {len(signals)}/{len(results)} 只可入场")
    for s in signals:
        print(f"  {s['code']} {s['name']}: {s['entry_reason']} | 止损 {s['stop_price']:.2f}({s['stop_pct']:+.1f}%) 仓位{s['pos_pct']:.0f}%")
else:
    print("[---] 今日无信号 — 13只全部处于空仓状态")
    print("  市场处调整阶段，等待Turtle突破/MA金叉/RSI回弹")

# Total portfolio check
total_pos = sum(r["pos_pct"] for r in results if r["entry_signal"] == "BUY")
print(f"\n  组合总仓位: {total_pos:.0f}%")
print(f"  更新日期: {results[0]['latest_date']}")
