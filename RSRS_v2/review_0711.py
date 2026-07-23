"""
RSRS 每日复盘 v2 - 2026-07-11（周六复盘周五数据）
"""
import sys, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_final_strategy import load_etf, build_panel, compute_rsrs, compute_vol_scaling

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL"}

print('='*60)
print('  RSRS 每日复盘 — 2026-07-11')
print('='*60)

# === 1. 检查最新数据日期 ===
print('\n📅 数据检查:')
last_dates = {}
for c in POOL:
    df = load_etf(c)
    ld = df['date'].iloc[-1]
    last_dates[c] = ld
    print(f'  {c:>6s} {POOL[c]:8s} -> {ld}')

# === 2. RSRS信号 ===
df_sig = load_etf("510300")
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, 1200, 0.7, -1.0)
zs_s = pd.Series(zs_raw, index=pd.to_datetime(df_sig['date'].values))

last_dt = zs_s.dropna().index[-1]
zscore = float(zs_s.dropna().iloc[-1])
z50 = float(zs_s.dropna().iloc[-50]) if len(zs_s.dropna()) >= 50 else None

# RSRS方向
if zscore >= 0.7:
    direction = '🟢 做多模式'
elif zscore <= -1.0:
    direction = '🔴 空仓模式'
elif zscore > 0:
    direction = '🟡 偏多（灰色区）'
elif zscore > -1.0:
    direction = '🟤 偏空（灰色区）'
else:
    direction = '🎯 接近空仓'

print(f'\n📡 RSRS 信号 (截至{last_dt.date()}):')
print(f'  z-score = {zscore:.2f}  |  50天前: {z50:.2f}')
print(f'  方向  -> {direction}')

# 近30天趋势
z30 = zs_s.dropna().iloc[-30:]
trend = '上升' if z30.iloc[-1] > z30.iloc[0] else '下降'
count_buy = (z30 >= 0.7).sum()
count_sell = (z30 <= -1.0).sum()
print(f'  近30日趋势: {trend}, 触发买入{count_buy}天, 触发卖出{count_sell}天')

# === 3. C63动量排行 ===
print(f'\n📊 C63动量排行 (截止{last_dt.date()}):')

raw, panel = build_panel(POOL, min_rows=200)
rb = 42
mom_list = []
for code, name in POOL.items():
    df = raw[code]
    s = df.set_index('date')['close']
    s = s[s.index.isin(panel.index)]
    if len(s) >= rb:
        ret = (s.iloc[-1] / s.iloc[-rb] - 1) * 100
        mom_list.append((code, name, ret))

mom_list.sort(key=lambda x: -x[2])
for i, (c, n, ret) in enumerate(mom_list, 1):
    icon = '✅' if i == 1 else ''
    pos_neg = '+' if ret > 0 else ''
    print(f'  {i:>2d}. {icon} {n:8s} {c:>6s}  {pos_neg}{ret:>+7.2f}%')

# === 4. 持仓复盘 ===
print(f'\n💼 持仓追踪: KC50 (588000)')
print(f'  买入日: 2026-06-24 | 买入价: 2.01')
print(f'  份数: 20,000 | 仓位: ~80%')
print(f'  锁仓到期: 2026-08-05 (剩余25天)')

# KC50价格
kc50 = load_etf('588000')
kc50 = kc50[kc50['date'] <= pd.Timestamp(last_dt)]
if len(kc50) > 0:
    kc50_px = float(kc50['close'].iloc[-1])
    kc50_px_date = kc50['date'].iloc[-1]
    
    buy_px = 2.01
    pnl_pct = (kc50_px / buy_px - 1) * 100
    pnl_amt = (kc50_px - buy_px) * 20000
    
    print(f'  最新价: {kc50_px:.3f} ({kc50_px_date.date()})')
    print(f'  浮动盈亏: {pnl_pct:+.2f}%  ({"💰 盈利" if pnl_pct > 0 else "💸 亏损"} +{pnl_amt:+.0f}元)')
    
    # 近5日价格走势
    print(f'  近5日走势:')
    for i in range(max(0, len(kc50)-5), len(kc50)):
        d = kc50.iloc[i]
        print(f'    {d["date"].date()}  {d["close"]:.3f}')
else:
    print(f'  数据不可用')

# === 5. 综合判断 ===
print(f'\n📋 综合判断:')
is_locked = True  # 锁仓至2026-08-05

if zscore <= -1.0:
    print(f'  ⚠️ RSRS翻空! 锁仓到期{"" if is_locked else "已过期"}')
    if not is_locked:
        print(f'  ❌ 清仓!')
elif is_locked:
    print(f'  🔒 锁仓期间，不动。')
    print(f'  📅 下次调仓日: 调仓周期RB=42天，约2026-08-05前后')
else:
    print(f'  🟢 锁仓已到期，RSRS信号 {direction}')
    print(f'  📊 KC50仍为C63第1名 → 继续持有')
    print(f'  📅 下次调仓日: 下次RB=42到期时重新排名')

print(f'\n  ⚠️ 提示: 置换检验对RSRS择时效果存疑，建议每季度做Walk Forward验证')
print(f'  报告: D:\\QClaw_Trading\\RSRS_v2\\RSRS稳健性验证_20260710.md')
print(f'='*60)
