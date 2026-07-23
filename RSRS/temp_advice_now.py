"""
RSRS+C63+波动率 - 今日信号（无emoji版，绕开GBK问题）
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'D:/QClaw_Trading/RSRS')
from rsrs_final_strategy import load_etf, build_panel, compute_rsrs, compute_vol_scaling

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}

df_sig = load_etf("510300")
M, buy, sell = 900, 0.7, -1.0
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

# 取最新数据
today = sig_s.index[-1]
last_date_str = str(df_sig["date"].iloc[-1])
print("=" * 70)
print("  RSRS + C63 + 波动率  --  今日信号  {}".format(today.strftime('%Y-%m-%d')))
print("=" * 70)
print("  RSRS z-score: {:.4f}".format(float(sig_s.iloc[-1])))
print("  买入阈值: >= 0.7")
print("  卖出阈值: <= -1.0")
print()

z_val = float(sig_s.iloc[-1])
if z_val >= buy:
    print("  >> 信号: 多头 (RSRS已触发买入)")
elif z_val <= sell:
    print("  >> 信号: 空头 (RSRS触发清仓)")
else:
    print("  >> 信号: 灰色区域 (等待)")

print()

# 计算波动率缩放仓位
raw, panel = build_panel(POOL, min_rows=200)
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)
last_sc = float(sc.loc[today]) if today in sc.index else 1.0
print("  目标波动率: 16%")
print("  波动率缩放因子: {:.4f}  (仓位上限90%)".format(last_sc))
print("  建议仓位: {:.0f}%".format(min(max(last_sc, 0.1), 0.9) * 100))
print()

# C63动量
mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

momentum = {}
for code in POOL:
    if today in mom[code].index:
        v = float(mom[code].loc[today])
        if not np.isnan(v):
            momentum[code] = v

rk = sorted(momentum.items(), key=lambda x: -x[1])
print("  C63动量排名 (63日收益):")
print("  {:>4s}  {:>8s}  {:>10s}".format("排名", "标的", "63d收益"))
for i, (c, v) in enumerate(rk, 1):
    print("  {:>4d}  {:>8s}  {:>+9.2f}%".format(i, POOL.get(c,c), v*100))

print()
print("  >> C63建议买入: ", end="")
pos_items = [c for c, v in rk if v > 0]
if pos_items:
    best = pos_items[0]
    print("{} (收益率 +{:.2f}%)".format(POOL.get(best, best), momentum[best]*100))
else:
    print("无正收益标的, 空仓")

print()

# 持仓检查
pos_df = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
hold, lr, lku = [], None, None
lock = 42
rb = 63

for dt in panel.index:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt]); eff = raw_s
    if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
    if eff == 0: hold, lku = [], None; continue
    if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock)
    if lr is None or (dt - lr).days >= rb:
        scs = {}
        for c in POOL:
            if dt in mom[c].index:
                v = float(mom[c].loc[dt])
                if not np.isnan(v): scs[c] = v
        if not scs: hold = []; continue
        rk2 = sorted(scs.items(), key=lambda x: -x[1])
        sel = [c for c,v_ in rk2 if v_>0]
        hold = sel[:1] if sel else []; lr = dt
    if hold:
        w = float(sc.loc[dt]) if dt in sc.index else 1.0
        if hold[0] in pos_df.columns: pos_df.loc[dt, hold[0]] = w

curr_pos = pos_df.loc[today]
has_pos = curr_pos.sum() > 0
if has_pos:
    for c in POOL:
        v = float(curr_pos.loc[c])
        if v > 0:
            print("  当前持仓: {} (仓位 {:.0f}%)".format(POOL.get(c,c), v*100))
else:
    print("  当前持仓: 空仓")

print()
print("  [操作建议]")
if z_val >= buy and pos_items:
    pct = min(max(last_sc, 0.1), 0.9) * 100
    best_name = POOL.get(pos_items[0], pos_items[0])
    print("    RSRS已翻多 (z-score={:.2f} >= 0.7)".format(z_val))
    print("    买入: {} 仓位约 {:.0f}%".format(best_name, pct))
    print("    锁仓: 42天（买入日起）")
    print("    下次调仓: 63天后")
elif z_val >= buy and not pos_items:
    print("    RSRS已翻多, 但池内无正收益标的, 空仓等待")
else:
    print("    RSRS未翻多, 继续空仓等待")
