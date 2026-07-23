"""
检查最新数据 + 当前买入建议
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)
DATA_DIR = "D:\\QClaw_Trading\\data"

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}

# 检查最新数据
print("最新数据日期检查:")
for code, name in POOL.items():
    with open(f"{DATA_DIR}/history/{code}.json","r",encoding="utf-8") as f:
        d = json.load(f)
    last = d["records"][-1]["date"]
    print(f"  {code} {name:<8} -> {last}")

# 运行策略信号
raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

M, rb, lock = 900, 63, 42
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
zs_s = pd.Series(zs_raw, index=pd.to_datetime(df_sig["date"].values))

latest = panel.index[-1]
print(f"\n统计截至: {latest.date()}")

# 态势判断
print(f"\n{'='*80}")
print(f"  当前市场态势 (RSRS x C63)")
print(f"{'='*80}")

zs = float(zs_s.loc[latest]) if latest in zs_s.index else 0
sig = int(sig_s.loc[latest]) if latest in sig_s.index else 0
print(f"\n  RSRS z-score: {zs:.2f}")
print(f"  信号: {'多头' if sig==1 else '空仓于'} (阈值: buy>=0.7, sell<=-1.0)")

if zs < -1.0:
    print(f"  → 极空: RSRS强烈看空, 不宜买入")
elif zs < 0.0:
    print(f"  → 偏空: z-score为负, 市场趋势偏弱, 等待为好")
elif zs < 0.7:
    print(f"  → 灰色区域: z-score为正但未触买入阈值, 等待0.7再入场更安全")
else:
    print(f"  → 多头: RSRS已触发买入, 按策略执行")

# 全池动量
print(f"\n  全池动量排名 (63日收益):")
print(f"  {'排名':>4} {'标的':<8} {'代码':>8} {'63d收益':>10} {'状态':<10}")
scores = []
for code in POOL:
    if latest in mom[code].index:
        v = float(mom[code].loc[latest])
        if not np.isnan(v): scores.append((code, POOL[code], v))
scores.sort(key=lambda x: -x[2])
for i, (c, nm, v) in enumerate(scores):
    chg = "+" if v>0 else ""
    print(f"  {i+1:>4}  {nm:<8} {c:>8} {chg}{v*100:>+7.2f}%")

# 策略回答核心问题
print(f"\n{'='*80}")
print(f"  回答: 空仓状态下, 现在适合买什么?")
print(f"{'='*80}")

# Scenario analysis
if zs >= 0.7:
    top_pos = [s for s in scores if s[2] > 0]
    if top_pos:
        print(f"\n  [OK] RSRS已触发买入(z-score={zs:.2f}>=0.7), 动量第1名是 {top_pos[0][1]}")
        print(f"  建议: 买入 {top_pos[0][1]} ({top_pos[0][0]}), {top_pos[0][2]*100:.1f}% 63d收益")
        print(f"  仓位: 波动率缩放后建议 ~{int(float(sc.loc[latest])*100) if latest in sc.index else 100}%")
elif zs < -1.0:
    print(f"\n  [NO] RSRS强烈看空(z-score={zs:.2f}), 空仓是正确的, 不建议买入")
elif zs < 0.0:
    print(f"\n  [!] 偏空(z-score={zs:.2f}<0), 现在入场风险较高")
    print(f"     建议等待z-score回升至0.7以上再入场")
else:
    # Gray zone: 0-0.7
    print(f"\n  [?] 灰色区域(z-score={zs:.2f}, 0~0.7)")
    print(f"     RSRS方向偏多但未确认, 策略规则=不操作")
    
    # What WOULD we buy if RSRS triggered?
    top_pos = [s for s in scores if s[2] > 0]
    if top_pos:
        print(f"     如果现在强行开仓: 动量第1名={top_pos[0][1]} ({top_pos[0][2]*100:.1f}%)")
    else:
        print(f"     所有标的63d收益为负, 即使开仓也无标的可选")
    
    # Check recent RSRS trend
    recent_zs = [zs_s.loc[d] for d in panel.index[-20:] if d in zs_s.index]
    trend = "上升" if len(recent_zs) > 5 and recent_zs[-1] > recent_zs[-5] else "下降"
    n_bear = sum(1 for z in recent_zs if z < -1.0)
    n_bull = sum(1 for z in recent_zs if z > 0.7)
    print(f"     近20日z-score趋势: {trend}")
    if n_bull > 0:
        print(f"     近20日有{n_bull}天触及买入阈值, z-score正在靠近0.7")
    print(f"     建议: 等待z-score >= 0.7再入场")
