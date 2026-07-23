"""
RSRS深度审计：数据质量 + 计算正确性 + 修正版z-score行为诊断
"""
import sys, os, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
sys.stdout.reconfigure(encoding='utf-8')
from rsrs_final_strategy import DATA_DIR

N, M = 18, 900

# ── 1. 数据质量检查 ──
print("=" * 90)
print("  1. 数据质量检查")
print("=" * 90)

with open(f"{DATA_DIR}\\510300.json","r",encoding="utf-8") as f:
    raw = json.load(f)
df = pd.DataFrame(raw["records"])
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

print(f"\n  510300数据范围: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")
print(f"  总行数: {len(df)}")
print(f"  列: {list(df.columns)}")

# 检查缺失值
print(f"\n  缺失值: {df.isnull().sum().to_dict()}")
# 检查重复日期
dup = df["date"].duplicated().sum()
print(f"  重复日期: {dup}")
# 检查异常价格
for col in ['open','close','high','low']:
    neg = (df[col] <= 0).sum()
    print(f"  {col}<=0: {neg}")
# 检查价格关系
bad_hl = (df["high"] < df["low"]).sum()
bad_ho = (df["high"] < df["open"]).sum() if 'open' in df.columns else 0
bad_lc = (df["low"] > df["close"]).sum() if 'close' in df.columns else 0
print(f"  high<low: {bad_hl}, high<open: {bad_ho}, low>close: {bad_lc}")
# chg字段
if 'chg' in df.columns:
    calc_chg = df['close'].pct_change() * 100
    diff = (df['chg'] - calc_chg).abs().max()
    print(f"  chg字段最大偏差: {diff:.4f}%")

# ── 2. 原版RSRS计算校验 ──
print("\n" + "=" * 90)
print("  2. RSRS原版计算正确性校验")
print("=" * 90)

high = df["high"].values.astype(float)
low = df["low"].values.astype(float)
close = df["close"].values

# 手动计算前10个有效beta，与替代方法对比
print("\n  前5个有效beta（手工 vs numpy polyfit vs lstsq）:")
count = 0
for i in range(N-1, len(df)):
    if count >= 5: break
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if np.isnan(x).any() or np.isnan(y).any(): continue
    
    # 方法1: lstsq
    A = np.column_stack([np.ones(N), x])
    b1 = np.linalg.lstsq(A, y, rcond=None)[0][1]
    
    # 方法2: polyfit (degree=1)
    b2 = np.polyfit(x, y, 1)[0]
    
    # 方法3: 公式法 β = cov(x,y)/var(x)
    xm, ym = x.mean(), y.mean()
    cov = np.sum((x-xm)*(y-ym))/(N-1)
    varx = np.sum((x-xm)**2)/(N-1)
    b3 = cov/varx if varx > 0 else 0
    
    print(f"  i={i} date={df['date'].iloc[i].date()}: lstsq={b1:.6f} polyfit={b2:.6f} formula={b3:.6f}  diff={abs(b1-b3):.2e}")
    count += 1

# 完整beta序列
beta_full = np.full(len(df), np.nan)
for i in range(N-1, len(df)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if not np.isnan(x).any() and not np.isnan(y).any():
        try: beta_full[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        except: pass

print(f"\n  beta统计: 有效={np.sum(~np.isnan(beta_full))}  均值={np.nanmean(beta_full):.4f}  std={np.nanstd(beta_full):.4f}")
print(f"  范围: [{np.nanmin(beta_full):.4f}, {np.nanmax(beta_full):.4f}]")

# z-score
zs_full = np.full(len(beta_full), np.nan)
for i in range(M-1, len(beta_full)):
    v = beta_full[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs_full[i]=(beta_full[i]-mu)/sg

# 检查z-score在最开始的分布
start_idx = M-1
print(f"\n  z-score统计(从第{M}天起): 有效={np.sum(~np.isnan(zs_full))}  mean={np.nanmean(zs_full):.4f}  std={np.nanstd(zs_full):.4f}")
print(f"  范围: [{np.nanmin(zs_full):.4f}, {np.nanmax(zs_full):.4f}]")
# z-score的标准化质量 - 理论上z-score的mean≈0, std≈1
zs_valid = zs_full[~np.isnan(zs_full)]
print(f"  z-score理论检查: mean={zs_valid.mean():.4f}(应≈0) std={zs_valid.std():.4f}(应≈1)")

# ── 3. 关键年份z-score和delta检查 ──
dates = df["date"].values
print("\n" + "=" * 90)
print("  3. 关键年份逐日z-score & beta轨迹")
print("=" * 90)

for yr_check in [2022]:
    print(f"\n  {yr_check}年关键信号节点:")
    # 找到当年所有有效的(z-score, beta, signal)对
    for i in range(len(df)):
        dt = pd.Timestamp(dates[i])
        if dt.year != yr_check: continue
        z = zs_full[i]
        if np.isnan(z): continue
        sig = 0
        sp = ""  # signal pattern
        if z > 0.7: sig = 1
        elif z < -1.0: sig = 0
        # 只打印信号变动的日子
        if i > 0:
            prev_z = zs_full[i-1]
            prev_sig = 0
            if not np.isnan(prev_z):
                if prev_z > 0.7: prev_sig = 1
                elif prev_z < -1.0: prev_sig = 0
            if sig != prev_sig or i == M:
                date_str = str(dt.date())
                b = beta_full[i]
                chg_pct = 0
                if i>0 and close[i-1]>0:
                    chg_pct = (close[i]/close[i-1]-1)*100
                sig_label = "LONG" if sig == 1 else "FLAT"
                prev_label = "LONG" if prev_sig == 1 else "FLAT"
                print(f"  {date_str}  beta={b:.4f}  z={z:+.2f}  {prev_label}→{sig_label}  HS300%={chg_pct:+.1f}%")

# ── 4. 验证修正版z-score失真 ──
print("\n" + "=" * 90)
print("  4. 修正版z-score失真诊断（MA=30为例）")
print("=" * 90)

def ma(arr, w):
    out = np.full_like(arr, np.nan)
    cs = np.cumsum(np.nan_to_num(arr))
    for i in range(w-1, len(arr)):
        out[i] = (cs[i] - (cs[i-w] if i>=w else 0)) / w
    return out

# 原版beta vs MA=30 beta 分布对比
high_sm30 = ma(high, 30)
low_sm30 = ma(low, 30)
beta_ma30 = np.full(len(df), np.nan)
for i in range(N-1, len(df)):
    y = high_sm30[i-N+1:i+1]; x = low_sm30[i-N+1:i+1]
    if np.isnan(x).any() or np.isnan(y).any(): continue
    try: beta_ma30[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
    except: pass

print(f"\n  beta统计对比:")
print(f"  原版:  有效={np.sum(~np.isnan(beta_full))}  mean={np.nanmean(beta_full):.4f}  std={np.nanstd(beta_full):.4f}")
print(f"  MA=30: 有效={np.sum(~np.isnan(beta_ma30))}  mean={np.nanmean(beta_ma30):.4f}  std={np.nanstd(beta_ma30):.4f}")
print(f"  MA30/原版 std比: {np.nanstd(beta_ma30)/np.nanstd(beta_full):.2f}x")

# MA=30 z-score
zs_ma30 = np.full(len(beta_ma30), np.nan)
for i in range(M-1, len(beta_ma30)):
    v = beta_ma30[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs_ma30[i]=(beta_ma30[i]-mu)/sg

print(f"\n  z-score统计对比:")
print(f"  原版:  mean={np.nanmean(zs_full):.4f}(应≈0)  std={np.nanstd(zs_full):.4f}(应≈1)  [{(np.nanmin(zs_full)):.2f}, {np.nanmax(zs_full):.2f}]")
print(f"  MA=30: mean={np.nanmean(zs_ma30):.4f}(应≈0)  std={np.nanstd(zs_ma30):.4f}(应≈1)  [{np.nanmin(zs_ma30):.2f}, {np.nanmax(zs_ma30):.2f}]")

# 2022年MA=30信号
print(f"\n  2022年 MA=30 信号变化:")
for i in range(len(df)):
    dt = pd.Timestamp(dates[i])
    if dt.year != 2022: continue
    z = zs_ma30[i]
    if np.isnan(z): continue
    sig = 0
    if z > 0.7: sig = 1
    elif z < -1.0: sig = 0
    if i > M:
        prev_z = zs_ma30[i-1]
        prev_sig = 0
        if not np.isnan(prev_z):
            if prev_z > 0.7: prev_sig = 1
            elif prev_z < -1.0: prev_sig = 0
        if sig != prev_sig:
            date_str = str(dt.date())
            sig_label = "LONG" if sig == 1 else "FLAT"
            prev_label = "LONG" if prev_sig == 1 else "FLAT"
            print(f"  {date_str}  z={z:+.2f}  {prev_label}→{sig_label}")

# ── 5. 验证方向乘数版z-score ──
print("\n" + "=" * 90)
print("  5. 方向乘数版beta/z-score分布")
print("=" * 90)

beta_dir = np.full(len(df), np.nan)
for i in range(N-1, len(df)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if np.isnan(x).any() or np.isnan(y).any(): continue
    try:
        b = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        beta_dir[i] = b * (1 if close[i] >= close[i-N+1] else -1)
    except: pass

zs_dir = np.full(len(beta_dir), np.nan)
for i in range(M-1, len(beta_dir)):
    v = beta_dir[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs_dir[i]=(beta_dir[i]-mu)/sg

print(f"\n  beta:  有效={np.sum(~np.isnan(beta_dir))}  mean={np.nanmean(beta_dir):.4f}  std={np.nanstd(beta_dir):.4f}")
print(f"        正beta占比: {np.sum(beta_dir > 0)/np.sum(~np.isnan(beta_dir))*100:.1f}%")
print(f"  z-score: mean={np.nanmean(zs_dir):.4f}(应≈0)  std={np.nanstd(zs_dir):.4f}(应≈1)  [{np.nanmin(zs_dir):.2f}, {np.nanmax(zs_dir):.2f}]")

# 2022年方向版信号
print(f"\n  2022年 方向乘数 信号变化:")
for i in range(len(df)):
    dt = pd.Timestamp(dates[i])
    if dt.year != 2022: continue
    z = zs_dir[i]
    if np.isnan(z): continue
    sig = 0
    if z > 0.7: sig = 1
    elif z < -1.0: sig = 0
    if i > M:
        prev_z = zs_dir[i-1]
        prev_sig = 0
        if not np.isnan(prev_z):
            if prev_z > 0.7: prev_sig = 1
            elif prev_z < -1.0: prev_sig = 0
        if sig != prev_sig:
            date_str = str(dt.date())
            sig_label = "LONG" if sig == 1 else "FLAT"
            prev_label = "LONG" if prev_sig == 1 else "FLAT"
            print(f"  {date_str}  z={z:+.2f}  {prev_label}→{sig_label}")

print("\n" + "=" * 90)
print("  审计完成")
print("=" * 90)
