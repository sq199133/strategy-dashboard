"""
RSRS vs 12-1时序动量择时 + 回撤止损风控 对比测试
==================================================

Test 1: 择时层对比
  A. 基线（RSRS择时）
  B. 沪深300 12-1时序动量择时（沪深300 12-1 > 0 → 做多）
  C. 单ETF 12-1时序动量（各自12-1 > 0才可入选）
  D. RSRS + ETF 12-1双条件（RSRS做多 + ETF 12-1 > 0才选）

Test 2: 月度回撤止损
  A. 基线 + 月亏>8%减半仓（可突破锁仓）
  B. 基线 + 月亏>15%全清
"""
import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_rsrs

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL","515080":"ZSHL"}

print("="*80)
print("  RSRS vs 12-1动量择时 + 回撤止损风控 对比测试")
print("="*80)

raw, panel = build_panel(POOL, min_rows=200)
print(f"\n  面板: {len(panel)}天, {len(POOL)}只ETF")
print(f"  日期: {panel.index[0].date()} ~ {panel.index[-1].date()}")

df_sig = load_etf("510300")

# ─── 63d动量(选股用) ───
mom63 = {}
for code, df in raw.items():
    s = df.set_index("date")["close"].pct_change(63)
    mom63[code] = s[s.index.isin(panel.index)]

# ─── 12-1动量(择时/选股用) ───
def calc_121(data_dict, lag1m=21, lag12m=252):
    result = {}
    for code, df in data_dict.items():
        dfi = df.set_index("date")["close"]
        val = dfi.shift(lag1m) / dfi.shift(lag12m) - 1
        result[code] = val[val.index.isin(panel.index)]
    return result

mom121_std = calc_121(raw, 21, 252)
hs300_121_std = mom121_std['510300']

# ─── 波动率缩放函数 ───
def get_vol_scale(dt):
    if dt not in df_sig.set_index("date").index:
        return 1.0
    dfi = df_sig.set_index("date")
    idx = dfi.index
    pos = idx.get_loc(dt) if dt in idx else -1
    if pos >= 70:
        slice_ = dfi.iloc[pos-69:pos+1]['close']
        dr = slice_.pct_change().dropna()
        av = dr.std() * np.sqrt(252)
        w = min(0.16 / av, 0.9) if av > 0.01 else 0.9
        return max(w, 0.1)
    return 1.0


def run_test(M=1200, buy=0.7, sell=-1.0, rb=42, lock=42,
             timing_mode='rsrs', stoploss_mode='none',
             no_neg=True, mom121_override=None):
    """
    timing_mode:
      'rsrs'       : 沪深300 RSRS
      'hs300_121'  : 沪深300 12-1动量
      'etf_121'    : 单ETF 12-1 > 0才进入选股池
      'rsrs_etf121': RSRS做多 + 仅选12-1>0的ETF

    stoploss_mode:
      'none' | 'mild' | 'hard'
    """
    mom121 = mom121_override if mom121_override is not None else mom121_std
    hs300_121 = mom121['510300']

    if timing_mode in ('rsrs', 'rsrs_etf121'):
        sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
        sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None

    # 净值跟踪用于止损
    sl_triggered = False

    for dt in panel.index:
        # ─── 1. 判断是否可以做多 ───
        can_long = True

        if timing_mode == 'rsrs':
            if dt not in sig_s.index:
                prev_long = can_long
                can_long = False
            else:
                prev_long = can_long
                raw_s = float(sig_s.loc[dt])
                if lock > 0 and lku and dt <= lku and raw_s == 0:
                    raw_s = 1.0
                can_long = (raw_s == 1)

            # 信号翻多即设锁仓起始（与原版pool10_backtest一致）
            if can_long and lock > 0 and lku is None:
                lku = dt + pd.Timedelta(days=lock)

        elif timing_mode == 'hs300_121':
            if dt not in hs300_121.index or np.isnan(hs300_121.loc[dt]):
                prev_long = can_long
                can_long = False
            else:
                prev_long = can_long
                can_long = hs300_121.loc[dt] > 0
                if lock > 0 and lku and dt <= lku and not can_long:
                    can_long = True

            # 锁仓: 信号翻多即设置锁仓起始
            if can_long and lock > 0 and lku is None:
                lku = dt + pd.Timedelta(days=lock)

        elif timing_mode == 'etf_121':
            can_long = True
            if can_long and lock > 0 and lku is None:
                lku = dt + pd.Timedelta(days=lock)

        elif timing_mode == 'rsrs_etf121':
            if dt not in sig_s.index:
                can_long = False
            else:
                raw_s = float(sig_s.loc[dt])
                if lock > 0 and lku and dt <= lku and raw_s == 0:
                    raw_s = 1.0
                can_long = (raw_s == 1)

            if can_long and lock > 0 and lku is None:
                lku = dt + pd.Timedelta(days=lock)

        # ─── 2. 止损检查 ───
        sl_cut = 1.0
        if stoploss_mode in ('mild', 'hard') and hold:
            # 近22天持仓标的的收益
            recent_idx = panel.index[panel.index <= dt][-23:]
            if len(recent_idx) >= 6:
                px = panel.loc[recent_idx, hold[0]]
                if len(px) >= 6:
                    rets = px.pct_change().dropna()
                    if len(rets) >= 5:
                        cum = (1 + rets[-22:]).prod() - 1
                        if stoploss_mode == 'mild' and cum < -0.08:
                            sl_cut = 0.5
                        elif stoploss_mode == 'hard' and cum < -0.15:
                            sl_cut = 0.0

        if not can_long or sl_cut <= 0:
            # 清仓时清除锁仓
            hold, lku = [], None
            continue

        # ─── 3. 选股 ───
        if lr is None or (dt - lr).days >= rb:
            scs = {}
            for c in POOL:
                if dt in mom63[c].index:
                    v = float(mom63[c].loc[dt])
                    if not np.isnan(v):
                        if timing_mode in ('etf_121', 'rsrs_etf121'):
                            if dt in mom121[c].index:
                                v121 = float(mom121[c].loc[dt])
                                if np.isnan(v121) or v121 <= 0:
                                    continue
                            else:
                                continue
                        scs[c] = v
            if not scs:
                hold = []
                continue

            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c, v in rk if v > 0] if no_neg else [c for c, v in rk]
            hold = sel[:1] if sel else []
            lr = dt
            sl_triggered = False

        if not hold:
            continue

        # ─── 4. 仓位 ───
        w = get_vol_scale(dt)
        if stoploss_mode in ('mild', 'hard'):
            w = w * sl_cut

        if hold[0] in pos.columns:
            pos.loc[dt, hold[0]] = w

    # ─── 绩效 ───
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)

    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20:
        return None

    eq = (1 + ret).cumprod()

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
    calmar = round(cagr*100/abs(mdd*100), 2) if mdd < 0 else 0
    total = round((eq.iloc[-1] - 1)*100, 1)
    avg_pos = pos[pos > 0].mean().mean() * 100 if (pos > 0).any().any() else 0

    return {
        "CAGR": round(cagr*100, 1), "Sharpe": round(sp, 2),
        "MDD": round(mdd*100, 1), "Total": total, "W%": round(wr, 1),
        "Pos%": round(pr, 1), "AvgPos%": round(avg_pos, 1),
        "Calmar": calmar, "Annual": annual
    }


# ══════════════════════════════════════
#  执行测试
# ══════════════════════════════════════

tests = [
    ("A. 基线(RSRS择时)",          {'timing_mode':'rsrs',       'stoploss_mode':'none'}),
    ("B. HS300 12-1择时",         {'timing_mode':'hs300_121',  'stoploss_mode':'none'}),
    ("C. 单ETF 12-1选股过滤",     {'timing_mode':'etf_121',    'stoploss_mode':'none'}),
    ("D. RSRS+ETF 12-1双过滤",    {'timing_mode':'rsrs_etf121','stoploss_mode':'none'}),
    ("E. 基线+月亏8%减半仓",      {'timing_mode':'rsrs',       'stoploss_mode':'mild'}),
    ("F. 基线+月亏15%全清",       {'timing_mode':'rsrs',       'stoploss_mode':'hard'}),
]

print(f"\n{'='*80}")
print(f"  Test 1+2: 择时层 + 止损风控 完整对比")
print(f"{'='*80}")
print(f"  {'方案':<28} {'CAGR%':>7} {'Sharpe':>7} {'MDD%':>6} {'Total%':>7} {'Pos%':>5} {'Calmar':>7}")
print(f"  {'-'*75}")

results = []
for label, kwargs in tests:
    r = run_test(M=1200, rb=42, lock=42, no_neg=True, **kwargs)
    results.append((label, r))
    if r:
        print(f"  {label:<28} {r['CAGR']:>6.1f}% {r['Sharpe']:>7.2f} {r['MDD']:>5.1f}% "
              f"{r['Total']:>6.1f}% {r['Pos%']:>4.0f}% {r['Calmar']:>6.2f}")

# 逐年
print(f"\n{'='*80}")
print(f"  逐年对比")
print(f"{'='*80}")
all_yrs = set()
for _, r in results:
    if r: all_yrs.update(r.get('Annual', {}).keys())
all_yrs = sorted(all_yrs)

header = "  " + f"{'年份':>6}"
for label, _ in tests:
    header += f"  {label[:8]:>8}"
print(header)
print(f"  {'-'*75}")

for yr in all_yrs:
    line = f"  {yr:>6}"
    for _, r in results:
        if r and yr in r.get('Annual', {}):
            line += f"  {r['Annual'][yr]:>7.1f}%"
        else:
            line += f"  {'':>8}"
    print(line)

# HS300 12-1 + 锁仓参数扫描
print(f"\n{'='*80}")
print(f"  HS300 12-1 + 不同锁仓期")
print(f"{'='*80}")
for lock_d in [0, 21, 42, 63, 84]:
    r = run_test(M=1200, rb=42, lock=lock_d, timing_mode='hs300_121', stoploss_mode='none')
    if r:
        print(f"  锁{lock_d:>3}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Total={r['Total']:>5.1f}%")

# 12-1窗口参数扫描
print(f"\n{'='*80}")
print(f"  12-1动量窗口调整")
print(f"{'='*80}")
for lag1m, lag12m in [(10,252), (21,252), (42,252), (21,378), (42,378)]:
    mom121_t = calc_121(raw, lag1m, lag12m)
    r = run_test(M=1200, rb=42, lock=42, timing_mode='hs300_121',
                 stoploss_mode='none', mom121_override=mom121_t)
    if r:
        print(f"  lag1m={lag1m:>3}d lag12m={lag12m:>3}d: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Total={r['Total']:>5.1f}%")

# 交叉组合
print(f"\n{'='*80}")
print(f"  交叉测试：12-1择时 + 止损")
print(f"{'='*80}")
for timing in ['hs300_121', 'etf_121']:
    for sl in ['none', 'mild', 'hard']:
        r = run_test(M=1200, rb=42, lock=42, timing_mode=timing, stoploss_mode=sl)
        if r:
            print(f"  {timing:<14} + {sl:<6}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Total={r['Total']:>5.1f}%")

# 保存
saved = {}
for label, r in results:
    if r: saved[label] = r
with open("D:\\QClaw_Trading\\RSRS\\rsrs_vs_12m1_results.json","w",encoding="utf-8") as f:
    json.dump(saved, f, ensure_ascii=False, indent=2)

print(f"\n{'='*80}")
print(f"  结果已保存")
