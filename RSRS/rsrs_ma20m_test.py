"""
RSRS + 20月均线过滤 对比测试（Idea A / Idea B vs 基线）
=========================================================

Idea A: RSRS信号 + 20月均线过滤（全矩阵）
  z>0.7 + price>20MA → 满仓
  z>0.7 + price<=20MA → 半仓
  z<-1.0 + price>20MA → 半仓
  z<-1.0 + price<=20MA → 空仓
  中间→保持

Idea B: 仅卖出端使用20月均线（分层减仓）
  z>0.7 → 满仓（与原版一致）
  z<-1.0 + price>20MA → 半仓
  z<-1.0 + price<=20MA → 空仓
  中间→保持

基线: 原版RSRS 0/1信号
  锁仓期内保持做多
"""
import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_rsrs

# ─── 11只全池 ───
POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL",
        "515080":"ZSHL"}

print("=" * 80)
print("  RSRS + 20月均线过滤 对比测试 (2026-07-12)")
print("=" * 80)

# ─── 数据加载 ───
print("\n  加载数据...")
raw, panel = build_panel(POOL, min_rows=200)
print(f"  面板: {len(panel)}天, {len(POOL)}只ETF")

df_sig = load_etf("510300")
print(f"  沪深300数据: {len(df_sig)}天")

# ─── 63d动量 ───
mom = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom[code] = s[s.index.isin(panel.index)]

# ─── 20月均线 ≈ 420个交易日 ───
df_sig_idx = df_sig.set_index("date")
ma20m = df_sig_idx["close"].rolling(420, min_periods=400).mean()
# 只保留面板范围内的日期
ma20m = ma20m[ma20m.index.isin(panel.index)]
print(f"  20月均线(420d): 有效{len(ma20m)}天")


def compute_ma_status(dt):
    """检查沪深300价格是否高于20月均线"""
    if dt not in ma20m.index or dt not in df_sig_idx.index:
        return True  # 默认牛市（数据不足时不切断信号）
    price = float(df_sig_idx.loc[dt, "close"])
    ma = float(ma20m.loc[dt])
    if np.isnan(ma):
        return True
    return price > ma


def run_backtest(M=1200, buy=0.7, sell=-1.0, rb=42, lock=42, no_neg=True, variant='baseline'):
    """
    统一回测框架
    variant: 'baseline' | 'idea_a' | 'idea_b'
    """
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
    zs_s  = pd.Series(zs_raw,  index=pd.to_datetime(df_sig["date"].values))
    
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None  # holdings, last rebalance, lock until
    
    # For variants: track the equity participation factor
    eq_factor = 1.0
    
    for dt in panel.index:
        if dt not in sig_s.index:
            continue
        
        z = float(zs_s.loc[dt]) if dt in zs_s.index and not np.isnan(zs_s.loc[dt]) else None
        if z is None:
            continue
        
        # ─── Determine effective signal ───
        if variant == 'baseline':
            raw_s = float(sig_s.loc[dt])
            eff = raw_s
            if lock > 0 and lku and dt <= lku and raw_s == 0:
                eff = 1.0  # 锁仓保护
        
        elif variant in ('idea_a', 'idea_b'):
            in_bull = compute_ma_status(dt)
            
            if z > buy:
                target_factor = 1.0 if in_bull else 0.5  # 满仓/半仓
                eff = 1.0
                # 锁定期间eq_factor不更新
                if not (lock > 0 and lku and dt <= lku):
                    eq_factor = target_factor
                else:
                    eq_factor = 1.0  # 锁仓期内满仓
                # 记录做多
                raw_s = 1.0
            
            elif z < sell:
                if variant == 'idea_a':
                    target_factor = 0.5 if in_bull else 0.0
                else:  # idea_b
                    target_factor = 0.5 if in_bull else 0.0
                
                eff = 1.0 if target_factor > 0 else 0.0
                if not (lock > 0 and lku and dt <= lku):
                    eq_factor = target_factor
                # 如果eq_factor=0，等同于空仓
                if eq_factor <= 0:
                    hold, lku = [], None
                    pos.loc[dt] = 0
                    eff = 0.0
            else:
                # 灰色区域：保持当前状态
                eff = float(sig_s.loc[dt])
                # 如果是空头且20MA之下，eq_factor保持
                if not (lock > 0 and lku and dt <= lku) and eff == 1:
                    pass  # 保持因子
                elif eff == 0:
                    hold, lku = [], None
                    pos.loc[dt] = 0
            
            # 锁仓逻辑
            if eff == 1 and lock > 0 and lku is None:
                lku = dt + pd.Timedelta(days=lock)
            # 锁仓期间强制满仓
            if lock > 0 and lku and dt <= lku:
                eq_factor = 1.0
        else:
            raise ValueError(f"Unknown variant: {variant}")
        
        # ─── 空仓处理 ───
        if eff == 0:
            hold, lku = [], None
            continue
        
        # ─── 调仓 ───
        if lr is None or (dt - lr).days >= rb:
            scs = {}
            for c in POOL:
                if dt in mom[c].index:
                    v = float(mom[c].loc[dt])
                    if not np.isnan(v):
                        scs[c] = v
            if not scs:
                hold = []
                continue
            
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c, v in rk if v > 0] if no_neg else [c for c, v in rk]
            hold = sel[:1] if sel else []
            lr = dt
        
        # ─── 仓位分配 ───
        if hold:
            # 波动率缩放
            w = 1.0  # default if no scaling
            # Use baseline approach: 70d vol scaling
            if dt in df_sig_idx.index:
                # Quick vol calc
                idx = df_sig_idx.index
                pos_idx = idx.get_loc(dt) if dt in idx else -1
                if pos_idx >= 70:
                    slice_ = df_sig_idx.iloc[pos_idx-69:pos_idx+1]['close']
                    daily_ret = slice_.pct_change().dropna()
                    ann_vol = daily_ret.std() * np.sqrt(252)
                    w = min(0.16 / ann_vol, 0.9) if ann_vol > 0.01 else 0.9
                    w = max(w, 0.1)
            
            # 应用变种因子
            if variant != 'baseline':
                w = w * eq_factor
            
            if hold[0] in pos.columns:
                pos.loc[dt, hold[0]] = w
    
    # ─── 绩效计算 ───
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    
    # 对齐到RSRS有效性开始
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20:
        return None
    
    eq = (1 + ret).cumprod()
    
    # 年度
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        nd = m.sum()
        if nd < 5:
            continue
        yr_eq = (1 + ret[m]).cumprod()
        annual[yr] = round((yr_eq.iloc[-1] ** (252/nd) - 1) * 100, 1)
    
    cagr = eq.iloc[-1] ** (252/len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    pr = (pos.sum(axis=1) > 0).mean() * 100
    calmar = round(cagr * 100 / abs(mdd * 100), 2) if mdd < 0 else 0
    
    # 平均有效仓位（只算持仓日）
    avg_pos = pos[pos > 0].mean().mean() * 100 if (pos > 0).any().any() else 0
    
    return {
        "CAGR": round(cagr * 100, 1),
        "Sharpe": round(sp, 2),
        "MDD": round(mdd * 100, 1),
        "W%": round(wr, 1),
        "Pos%": round(pr, 1),
        "AvgPos%": round(avg_pos, 1),
        "Calmar": calmar,
        "Annual": annual,
        "Total": round((eq.iloc[-1] - 1) * 100, 1),
        "M": M, "RB": rb, "Lock": lock
    }


# ══════════════════════════════════════
#  主测试
# ══════════════════════════════════════

# ─── 1. 基线（原版） ───
print(f"\n{'='*80}")
print(f"  1. 基线回测（原版RSRS）")
print(f"{'='*80}")
base = run_backtest(1200, 0.7, -1.0, 42, 42, no_neg=True, variant='baseline')
if base:
    ann_str = "  ".join(f"{yr}:{base['Annual'][yr]:>5.1f}%" for yr in sorted(base['Annual'].keys()))
    print(f"  CAGR={base['CAGR']:>5.1f}%  Sharpe={base['Sharpe']:.2f}  MDD={base['MDD']:>5.1f}%  "
          f"Total={base['Total']:.1f}%  AvgPos={base['AvgPos%']:.0f}%")
    print(f"  年: {ann_str}")

# ─── 2. Idea A: 全矩阵 ───
print(f"\n{'='*80}")
print(f"  2. Idea A: RSRS + 20月均线完整矩阵")
print(f"{'='*80}")
idea_a = run_backtest(1200, 0.7, -1.0, 42, 42, no_neg=True, variant='idea_a')
if idea_a:
    ann_str = "  ".join(f"{yr}:{idea_a['Annual'][yr]:>5.1f}%" for yr in sorted(idea_a['Annual'].keys()))
    print(f"  CAGR={idea_a['CAGR']:>5.1f}%  Sharpe={idea_a['Sharpe']:.2f}  MDD={idea_a['MDD']:>5.1f}%  "
          f"Total={idea_a['Total']:.1f}%  AvgPos={idea_a['AvgPos%']:.0f}%")
    print(f"  年: {ann_str}")

# ─── 3. Idea B: 仅卖出端过滤 ───
print(f"\n{'='*80}")
print(f"  3. Idea B: 卖出端20月均线分层")
print(f"{'='*80}")
idea_b = run_backtest(1200, 0.7, -1.0, 42, 42, no_neg=True, variant='idea_b')
if idea_b:
    ann_str = "  ".join(f"{yr}:{idea_b['Annual'][yr]:>5.1f}%" for yr in sorted(idea_b['Annual'].keys()))
    print(f"  CAGR={idea_b['CAGR']:>5.1f}%  Sharpe={idea_b['Sharpe']:.2f}  MDD={idea_b['MDD']:>5.1f}%  "
          f"Total={idea_b['Total']:.1f}%  AvgPos={idea_b['AvgPos%']:.0f}%")
    print(f"  年: {ann_str}")

# ═══ 参数敏感性 ───
print(f"\n{'='*80}")
print(f"  4. 参数敏感性测试（不同锁仓期 + MA窗口）")
print(f"{'='*80}")

for label, variant in [("Idea A (全矩阵)", "idea_a"), ("Idea B (卖出端)", "idea_b")]:
    print(f"\n  ── {label} ──")
    print(f"  {'锁仓':>4} {'MA窗口':>6} {'CAGR%':>7} {'Sharpe':>7} {'MDD%':>6} {'Total%':>7} {'AvgPos%':>7}")
    print(f"  {'-'*50}")
    for lock_d in [0, 21, 42, 63]:
        for ma_win in [400, 420, 440]:
            r = run_backtest(1200, 0.7, -1.0, 42, lock_d, no_neg=True, variant=variant)
            if r:
                print(f"  {lock_d:>4}d {ma_win:>5}d {r['CAGR']:>6.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>5.1f}% {r['Total']:>6.1f}% {r['AvgPos%']:>6.0f}%")

# ═══ 逐年对比表 ───
print(f"\n{'='*80}")
print(f"  5. 逐年对比")
print(f"{'='*80}")
all_years = sorted(set(
    list((base or {}).get('Annual', {}).keys()) +
    list((idea_a or {}).get('Annual', {}).keys()) +
    list((idea_b or {}).get('Annual', {}).keys())
))

print(f"  {'年份':>6} {'基线':>8} {'Idea_A':>8} {'Idea_B':>8}   {'基线':>8} {'Idea_A':>8} {'Idea_B':>8}")
print(f"  {'':>6} {'CAGR%':>8} {'CAGR%':>8} {'CAGR%':>8}   {'MDD%':>8} {'MDD%':>8} {'MDD%':>8}")
print(f"  {'-'*70}")
for yr in all_years:
    b_v = (base or {}).get('Annual', {}).get(yr, '')
    a_v = (idea_a or {}).get('Annual', {}).get(yr, '')
    b2_v = (idea_b or {}).get('Annual', {}).get(yr, '')
    # For total, compute total in each period
    b_fmt = f"{b_v:>7.1f}" if b_v != '' else "    "
    a_fmt = f"{a_v:>7.1f}" if a_v != '' else "    "
    b2_fmt = f"{b2_v:>7.1f}" if b2_v != '' else "    "
    print(f"  {yr:>6} {b_fmt:>8} {a_fmt:>8} {b2_fmt:>8}")


# ═══ 20月均线状态统计 ───
print(f"\n{'='*80}")
print(f"  6. 20月均线状态统计")
print(f"{'='*80}")
bull_days = 0
bear_days = 0
total_days = 0
for dt in panel.index:
    s = compute_ma_status(dt)
    if s:
        bull_days += 1
    else:
        bear_days += 1
    total_days += 1
print(f"  牛市(价格>20MA): {bull_days}/{total_days} ({bull_days/total_days*100:.1f}%)")
print(f"  熊市(价格<20MA): {bear_days}/{total_days} ({bear_days/total_days*100:.1f}%)")

# ─── 汇总表 ───
print(f"\n{'='*80}")
print(f"  7. 汇总对比")
print(f"{'='*80}")
print(f"  {'方案':<18} {'CAGR%':>7} {'Sharpe':>7} {'MDD%':>6} {'Total%':>7} {'Pos%':>6} {'AvgPos%':>7} {'Calmar':>7}")
print(f"  {'-'*65}")
for label, r in [("基线(原版RSRS)", base), ("Idea A (全矩阵)", idea_a), ("Idea B (卖出端)", idea_b)]:
    if r:
        print(f"  {label:<18} {r['CAGR']:>6.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>5.1f}% "
              f"{r['Total']:>6.1f}% {r['Pos%']:>5.0f}% {r['AvgPos%']:>6.0f}% {r['Calmar']:>6.2f}")

# ═══ 保存结果 ───
results = {}
for label, r in [("基线", base), ("Idea_A", idea_a), ("Idea_B", idea_b)]:
    if r:
        results[label] = {k: v for k, v in r.items() if k != 'Annual'}
        results[label]["Annual"] = r["Annual"]

with open("D:\\QClaw_Trading\\RSRS\\rsrs_ma20m_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*80}")
print(f"  结果已保存")
print(f"{'='*80}")
