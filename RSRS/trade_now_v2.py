"""
当前持仓信号：M=900 RB=63 Lock=42
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}
raw, panel = build_panel(POOL, min_rows=200)
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

# Run strategy
M, rb, lock = 900, 63, 42
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
zs_s = pd.Series(zs_raw, index=pd.to_datetime(df_sig["date"].values))

pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
hold, lr, lku, lk_start = [], None, None, None
rebal_log = []

for dt in panel.index:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    eff = raw_s
    if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
    if eff == 0: hold, lku, lk_start = [], None, None; continue
    if lock > 0 and raw_s == 1 and lku is None:
        lku = dt + pd.Timedelta(days=lock)
        lk_start = dt
    if lr is None or (dt - lr).days >= rb:
        scs = {}
        for c in POOL:
            if dt in mom[c].index:
                v = float(mom[c].loc[dt])
                if not np.isnan(v): scs[c] = v
        if not scs: hold = []; continue
        rk = sorted(scs.items(), key=lambda x: -x[1])
        sel = [c for c,v in rk if v>0]
        hold_new = sel[:1] if sel else []
        rebal_log.append({
            "date": dt, "zscore": round(float(zs_s.loc[dt]), 2),
            "signal": int(raw_s), "eff": int(eff),
            "target": hold_new[0] if hold_new else "FLAT",
            "target_name": POOL.get(hold_new[0], "FLAT") if hold_new else "FLAT",
            "locked": bool(lku and dt <= lku),
            "lock_until": str(lku.date()) if lku else "None"
        })
        hold = hold_new
        lr = dt
    if hold:
        w = float(sc.loc[dt]) if dt in sc.index else 1.0
        if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w

# Latest state
latest = panel.index[-1]
latest_raw_s = float(sig_s.loc[latest]) if latest in sig_s.index else 0
latest_zs = float(zs_s.loc[latest]) if latest in zs_s.index else 0

SEP = "="*80
print(SEP)
print("  RSRS x C63 - 当前信号")
print(SEP)

print(f"\n  信号日期: {latest.date()}")
print(f"  RSRS z-score: {latest_zs:.2f}  (买入>=0.7, 卖出<=-1.0)")
print(f"  RSRS信号: {'多头(1)' if latest_raw_s == 1 else '空仓(0)'}")
print(f"  Lock状态: {'锁定中' if (lku and latest <= lku) else '无'}", end="")
if lku and latest <= lku:
    print(f" (到期日: {lku.date()})")
else:
    print()

# Current holding
active = pos.loc[latest][pos.loc[latest] > 0]
if len(active) > 0:
    code = active.index[0]
    wgt = float(active.iloc[0])
    latest_sc = float(sc.loc[latest]) if latest in sc.index else 1.0
    print(f"\n  持仓: {POOL[code]} ({code})  仓位: {wgt*100:.0f}%")
    print(f"  波动率缩放因子: {latest_sc:.3f}")
else:
    print(f"\n  持仓: 空仓")

# Recent status
print(f"\n  最近5次调仓:")
for r in rebal_log[-5:]:
    dt = r["date"].date()
    zs = r["zscore"]
    target = r["target_name"]
    locked = r["locked"]
    lu = r["lock_until"]
    print(f"    {dt}  zs={zs:+.2f}  -> {target}  {'[锁]' if locked else '[无锁]'}  lock_until={lu}")

# Current momentum ranking
print(f"\n  全池动量排名 (63d):")
scores = []
for code in POOL:
    if latest in mom[code].index:
        v = float(mom[code].loc[latest])
        if not np.isnan(v): scores.append((code, POOL[code], v))
scores.sort(key=lambda x: -x[2])
for i, (c, nm, v) in enumerate(scores):
    cur = " <<< 当前持仓" if len(active) > 0 and c == active.index[0] else ""
    print(f"    {i+1}. {nm:<8} ({c})  {v*100:+.2f}%{cur}")

print(SEP)
print("  建议")
print(SEP)

if len(active) > 0 and latest_raw_s == 1:
    last_rebal = rebal_log[-1]["date"] if rebal_log else latest
    days_since = (latest - last_rebal).days
    next_rebal = last_rebal + pd.Timedelta(days=rb) if last_rebal else latest + pd.Timedelta(days=rb)
    print(f"\n  持有 {POOL[active.index[0]]} ({active.index[0]})")
    print(f"  仓位: {float(active.iloc[0])*100:.0f}%")
    print(f"  上次调仓: {last_rebal.date()} ({days_since}天前)")
    print(f"  下次调仓日: ~{next_rebal.date()}")
    print(f"\n  操作: 持仓不动")
elif latest_raw_s == 0:
    print(f"\n  RSRS空仓信号, 建议空仓等待")
else:
    print(f"\n  灰色区域 (z-score > -1.0且<0.7)")

# Save signal
signal = {
    "date": str(latest.date()),
    "rsrs_zscore": round(latest_zs, 2),
    "rsrs_signal": "long" if latest_raw_s == 1 else "flat",
    "lock_active": bool(lku and latest <= lku),
    "holdings": [{"code": active.index[0], "name": POOL[active.index[0]], "weight": round(float(active.iloc[0]), 3)}] if len(active) > 0 else [],
    "momentum_ranking": [{"code": c, "name": POOL[c], "ret63": round(v, 4)} for c,nm,v in scores],
}
with open("D:\\QClaw_Trading\\RSRS\\trade_signal_latest.json","w",encoding="utf-8") as f:
    json.dump(signal, f, ensure_ascii=False, indent=2)
fpath = "D:\\QClaw_Trading\\RSRS\\trade_signal_latest.json"
print(f"\n  信号已保存: {fpath}")
