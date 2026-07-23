"""
策略审计：逻辑 + 数据完整性检查
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

print("="*70)
print("  检查1: RSRS信号计算")
print("="*70)

M, rb, lock = 900, 63, 42
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
zs_s = pd.Series(zs_raw, index=pd.to_datetime(df_sig["date"].values))

print(f"  RSRS信号范围: {sig_s.index[0].date()} - {sig_s.index[-1].date()}")
print(f"  总trading days: {len(sig_s)}")
print(f"  前{M}天用于z-score: {len(zs_s.dropna())} valid z-scores")
print(f"  M={M}后第一天: {sig_s.index[M].date()}")
print(f"  信号分布: 多头={sum(1 for v in sig_s[M:] if v==1)} ({(sum(1 for v in sig_s[M:] if v==1)/(len(sig_s)-M)*100):.0f}%)")
print(f"          空仓={sum(1 for v in sig_s[M:] if v==0)}")

print(f"\n{'='*70}")
print(f"  检查2: 锁仓逻辑")
print(f"{'='*70}")

# Simulate lock logic on a small window
# Pick a known 0→1 transition
test_start = pd.Timestamp("2025-01-01")
test_end = pd.Timestamp("2025-06-30")
test_dates = [d for d in panel.index if test_start <= d <= test_end]
print(f"  测试窗口: {test_start.date()} - {test_end.date()} ({len(test_dates)}天)")

hold, lr, lku = [], None, None
lock_events = 0
lock_ignores = 0
for dt in test_dates:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    eff = raw_s
    was_locked = False
    if lock > 0 and lku and dt <= lku:
        was_locked = True
        if raw_s == 0: 
            lock_ignores += 1
            eff = 1.0
    if eff == 0: hold, lku = [], None; continue
    if lock > 0 and raw_s == 1 and lku is None: 
        lku = dt + pd.Timedelta(days=lock)
        lock_events += 1
    if lr is None or (dt - lr).days >= rb:
        hold = ["NSDQ" if dt.month % 2 == 0 else "GOLD"]  # Placeholder
        lr = dt

print(f"  锁仓触发: {lock_events}次")
print(f"  锁仓期间忽略空仓: {lock_ignores}次")

# Spot check specific dates
print(f"\n  锁仓事件时间线:")
for dt in test_dates:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    # Check for lock start
    if lock > 0 and raw_s == 1 and (lku is None or dt > lku):
        print(f"    锁仓开始: {dt.date()} (z-score={zs_s.loc[dt]:.2f})")
        lku_calc = dt + pd.Timedelta(days=lock)
        print(f"    锁仓到期: {lku_calc.date()}")
        lku = lku_calc
    if lku and dt > lku:
        lku = None

print(f"\n{'='*70}")
print(f"  检查3: 动量计算")
print(f"{'='*70}")

# For a given date, check what the momentum says for all ETFs
check_dates = [pd.Timestamp("2025-03-01"), pd.Timestamp("2025-06-01"), pd.Timestamp("2025-09-01")]
for cd in check_dates:
    # Find nearest date in panel
    avail_dates = [d for d in panel.index if d <= cd + pd.Timedelta(days=5)]
    if not avail_dates: continue
    actual_dt = avail_dates[-1]
    print(f"\n  日期: {actual_dt.date()} (目标: {cd.date()})")
    print(f"  RSRS信号: {int(sig_s.loc[actual_dt])}, z-score={zs_s.loc[actual_dt]:.2f}")
    
    scores = []
    for code, df in raw.items():
        s = df.set_index("date")["close"].pct_change(63)
        if actual_dt in s.index:
            v = s.loc[actual_dt]
            if not np.isnan(v):
                scores.append((code, POOL[code], v))
    scores.sort(key=lambda x: -x[2])
    print(f"  动量排名:")
    for i, (c, nm, v) in enumerate(scores[:5]):
        print(f"    {i+1}. {c} {nm}: +{v*100:.2f}%" if v>0 else f"    {i+1}. {c} {nm}: {v*100:.2f}%")
    top_pos = [s for s in scores if s[2] > 0]
    print(f"  正动量ETF数: {len(top_pos)}/{len(scores)}")
    if top_pos:
        print(f"  → 买入: {top_pos[0][1]} ({top_pos[0][0]}, +{top_pos[0][2]*100:.2f}%)")

print(f"\n{'='*70}")
print(f"  检查4: 2024年零收益原因")
print(f"{'='*70}")

sig_raw2, zs_raw2, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
sig_s2 = pd.Series(sig_raw2, index=pd.to_datetime(df_sig["date"].values))

yr = 2024
dates_2024 = [d for d in panel.index if d.year == yr]
long_in_2024 = [d for d in dates_2024 if d in sig_s2.index and float(sig_s2.loc[d]) == 1]
flat_in_2024 = [d for d in dates_2024 if d in sig_s2.index and float(sig_s2.loc[d]) == 0]
print(f"  2024年: 总交易日={len(dates_2024)}")
print(f"          RSRS多头={len(long_in_2024)}天 ({len(long_in_2024)/len(dates_2024)*100:.0f}%)")
print(f"          RSRS空仓={len(flat_in_2024)}天 ({len(flat_in_2024)/len(dates_2024)*100:.0f}%)")

# 检查2024年各ETF的表现
print(f"\n  2024年各ETF表现 (全年度):")
for code, df in raw.items():
    s = df.set_index("date")["close"]
    yr_data = s[s.index.year == yr]
    if len(yr_data) > 10:
        ret = (yr_data.iloc[-1] / yr_data.iloc[0] - 1) * 100
        print(f"    {code} {POOL[code]:<8}: {ret:+.1f}%")

# 检查2024年策略实际持有期的ETF表现
print(f"\n  2024年RSRS多头期间各ETF表现:")
for code, df in raw.items():
    s = df.set_index("date")["close"]
    if long_in_2024:
        start_val = s.loc[long_in_2024[0]] if long_in_2024[0] in s.index else None
        end_val = s.loc[long_in_2024[-1]] if long_in_2024[-1] in s.index else None
        if start_val and end_val:
            ret = (end_val/start_val - 1) * 100
            print(f"    {code} {POOL[code]:<8}: {ret:+.1f}% ({long_in_2024[0].date()} → {long_in_2024[-1].date()})")

print(f"\n{'='*70}")
print(f"  检查5: 数据完整性")
print(f"{'='*70}")

for code, df in raw.items():
    s = df.set_index("date")["close"]
    orig = len(s)
    dup = s.index.duplicated().sum()
    miss = s.isna().sum()
    neg = (s <= 0).sum()
    print(f"  {code} {POOL[code]:<8}: 记录={orig:>5}  重复日期={dup:>3}  NA值={miss:>3}  负价格={neg:>3}")

print(f"\n{'='*70}")
print(f"  检查6: Lock和Rebalance交互逻辑")
print(f"{'='*70}")

# Check: does lock get refreshed when RSRS stays above threshold?
lock_test_start = pd.Timestamp("2025-01-01")
lku = None
lock_refreshes = 0
for dt in [d for d in panel.index if d >= lock_test_start]:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    eff = raw_s
    if lock > 0 and lku and dt <= lku:
        if raw_s == 0: eff = 1.0
    if eff == 0: lku = None; continue
    if lock > 0 and raw_s == 1 and lku is None:
        lku = dt + pd.Timedelta(days=lock)
        lock_refreshes += 1

print(f"  2025年起锁仓刷新次数: {lock_refreshes}")

# Check: rebalance within lock period
print(f"\n  调仓日锁仓状态检查:")
lr_test = None
lku_test = None
aligned = 0
misaligned = 0
for dt in [d for d in panel.index if d >= pd.Timestamp("2020-01-01")]:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    if lock > 0 and lku_test and dt <= lku_test and raw_s == 0:
        eff = 1.0
    else:
        eff = raw_s
    if eff == 0: lku_test = None
    if lock > 0 and raw_s == 1 and lku_test is None:
        lku_test = dt + pd.Timedelta(days=lock)
    if lr_test is None or (dt - lr_test).days >= rb:
        lr_test = dt
        if lku_test and dt <= lku_test:
            aligned += 1
        elif eff == 1:
            aligned += 1
        else:
            misaligned += 1

print(f"  调仓发生在有效信号内: {aligned}次")
print(f"  调仓发生在信号外: {misaligned}次")

print(f"\n{'='*70}")
print(f"  审计完成")
print(f"{'='*70}")
