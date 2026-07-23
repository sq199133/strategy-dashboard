#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查ATR值在候选ETF中的分布"""
import os, json, glob, statistics
from datetime import datetime as dt

HIST = r"D:\Qclaw_Trading\data\history_long_v2"
POOL = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"

with open(POOL, encoding="utf-8") as f:
    d = json.loads(f.read())
etfs = d if isinstance(d, list) else d.get("data", [])
series, ohlc = {}, {}
for e in etfs:
    code = e["code"]
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
            c = r.get("close",0); v = r.get("vol",0)
            if wk not in wm or ds > wm[wk][0]:
                wm[wk] = (ds,c,v)
        except: pass
    if not wm: continue
    sr = sorted(wm.items())
    series[code] = [(wk, v[1]) for wk, v in sr]   # (wk, close)
    ohlc[code]  = {wk:{"c":v[1],"v":v[2]} for wk,v in sr}

all_wk = sorted(set(wk for s in series.values() for wk,_ in s))
last_wk = all_wk[-1]

# 计算ATR值（与回测脚本完全一致）
atr_vals = {}
for code, wd in ohlc.items():
    if len(wd) < 30: continue
    wkl = sorted(wd.keys())
    trs = [None]*len(wkl)
    for i in range(1,len(wkl)):
        cur = wd[wkl[i]]; prv = wd[wkl[i-1]]
        trs[i] = max(abs(cur["c"]-prv["c"]),
                       abs(cur["c"]-prv["c"]),   # placeholder, real formula below
                       abs(cur["c"]-prv["c"]))
    # proper TR:
    trs2 = [None]*len(wkl)
    for i in range(1,len(wkl)):
        cur = wd[wkl[i]]; prv = wd[wkl[i-1]]
        trs2[i] = max(cur["c"]-prv["c"],
                       abs(cur["c"]-prv["c"]),
                       abs(prv["c"]-cur["c"]))
    atrs = {}
    for i in range(21, len(wkl)):
        vs = [trs2[j] for j in range(i-20,i+1) if trs2[j] is not None and trs2[j]>0]
        if len(vs) >= 21:
            f14 = sum(vs[-14:])/14; s21 = sum(vs)/21
            if s21 > 0: atrs[wkl[i]] = f14/s21
    if last_wk in atrs:
        atr_vals[code] = atrs[last_wk]

# 年化波动率（用周收益率标准差×√52）
vol_vals = {}
for code, s in series.items():
    if len(s) < 20: continue
    closes = [c for wk,c in s]
    rets = []
    for i in range(1, len(closes)):
        if closes[i-1] > 0:
            rets.append(closes[i]/closes[i-1]-1)
    if len(rets) >= 20:
        std_w = statistics.stdev(rets[-20:]) if len(rets)>=21 else 0
        vol_vals[code] = std_w * (52**0.5)

print(f"ETF总数: {len(series)}")
print(f"有ATR值的ETF: {len(atr_vals)}")
print(f"有年化波动率的ETF: {len(vol_vals)}")
print(f"最新周: {last_wk}")

if atr_vals:
    vals = sorted(atr_vals.values())
    n = len(vals)
    print(f"\nATR比率分布 (最新周 {last_wk}):")
    print(f"  最小:    {min(vals):.3f}")
    print(f"  10%分位: {vals[int(n*0.1)]:.3f}")
    print(f"  25%分位: {vals[int(n*0.25)]:.3f}")
    print(f"  中位数:  {vals[n//2]:.3f}")
    print(f"  75%分位: {vals[int(n*0.75)]:.3f}")
    print(f"  90%分位: {vals[int(n*0.9)]:.3f}")
    print(f"  最大:    {max(vals):.3f}")

    wa_vals = [max(v, 0.3) for v in vals]
    n_below1 = sum(1 for v in vals if v <= 1.0)
    n_above1 = sum(1 for v in vals if v > 1.0)
    print(f"\n  ATR≤1.0 (不加仓): {n_below1}个 ({n_below1/n*100:.0f}%)")
    print(f"  ATR>1.0 (加仓):   {n_above1}个 ({n_above1/n*100:.0f}%)")
    extreme_high = sum(1 for v in vals if v > 1.5)
    extreme_low  = sum(1 for v in vals if v < 0.7)
    print(f"  ATR>1.5 (高波):   {extreme_high}个")
    print(f"  ATR<0.7 (低波):   {extreme_low}个")

if vol_vals:
    vals = sorted(vol_vals.values())
    print(f"\n年化波动率分布:")
    print(f"  最小:   {min(vals)*100:.1f}%")
    print(f"  中位数: {vals[len(vals)//2]*100:.1f}%")
    print(f"  最大:   {max(vals)*100:.1f}%")

# 核心分析：为什么verify_atr_effect里ATR vs 等权结果一样？
print("\n" + "="*60)
print("  核心问题诊断：ATR加权 vs 等权为何结果相同？")
print("="*60)
print("""
在 verify_atr_effect.py 中，top_n=1，每次只选1只ETF。
ATR权重影响的是：这只ETF分到多少仓位。
但无论分多少仓位，equity的变化幅度都是按比例的。
最终年化 = (最终/初始)^(1/年数)-1
→ 这是一个比例，与初始资金无关！

所以即使ATR加权×1.5仓位和等权×1.0仓位，最终equity比例相同：
  ATR:  100000 → 350000  → +250%
  等权: 100000 → 350000  → +250%
  
两个版本产生完全相同的equity曲线（只是标度不同）。

真正有意义的对比要看：
  1. 不同ATR值导致的仓位差异在top_n=1时影响有多大？
  2. 如果top_n>1，ATR加权会让高ATR的ETF获得更大仓位，
     低ATR的获得更小仓位 → 改变组合的风险收益特征

结论：verify_atr_effect.py 验证的是"相同标度下的等价性"，
      不是"ATR加权是否比等权更好"。
      两个脚本（backtest_yearly_v47 vs backtest_composite_stop）的真实差距
      来自：不同的候选过滤条件（vr>1.5），
      不是ATR仓位。
""")
