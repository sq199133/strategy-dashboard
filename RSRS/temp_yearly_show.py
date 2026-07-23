"""
RSRS+C63+波动率 - 分年回测展示
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'D:/QClaw_Trading/RSRS')
from rsrs_final_strategy import load_etf, build_panel, compute_rsrs, compute_vol_scaling

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

M, rb, lock = 900, 63, 42
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
hold, lr, lku = [], None, None

for dt in panel.index:
    if dt not in sig_s.index: continue
    raw_s = float(sig_s.loc[dt])
    eff = raw_s
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
        rk = sorted(scs.items(), key=lambda x: -x[1])
        sel = [c for c,v in rk if v>0]
        hold = sel[:1] if sel else []; lr = dt
    if hold:
        w = float(sc.loc[dt]) if dt in sc.index else 1.0
        if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w

dr = panel.pct_change().fillna(0)
ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
fs = pd.to_datetime(df_sig["date"].iloc[M])
ret = ret[ret.index >= fs]
eq = (1 + ret).cumprod()
total_ret = float(eq.iloc[-1]) - 1
nd = len(ret)
cagr = float(eq.iloc[-1]**(252/nd) - 1) * 100
sharp = float(np.sqrt(252) * ret.mean() / ret.std())
mdd = float((eq / eq.cummax() - 1).min() * 100)

last_date = str(ret.index[-1].strftime('%Y-%m-%d'))

# 打印表格
sep = "=" * 80
print(sep)
print("  RSRS + C63 + 波动率缩放  回测分年统计")
print("  标的池: 10只宽基  |  M=900  RB=63  锁42d  Top1  目标波16%")
print("  数据截至: " + last_date)
print(sep)

header = "{:>6s}  {:>6s}  {:>10s}  {:>10s}  {:>8s}  {:>6s}  {:>8s}  {:>8s}".format(
    "年份", "交易日", "年化CAGR", "实际收益", "波动率", "胜率", "最大回撤", "持有标")
print(header)
print("-" * 80)

for yr in sorted(set(d.year for d in ret.index)):
    m = ret.index.year == yr
    nd_yr = m.sum()
    if nd_yr < 5: continue
    yr_r = ret[m]
    yr_e = (1 + yr_r).cumprod()
    yr_cagr = (float(yr_e.iloc[-1])**(252/nd_yr) - 1) * 100
    yr_tot = (float(yr_e.iloc[-1]) - 1) * 100
    yr_vol = np.sqrt(252) * float(yr_r.std()) * 100
    yr_wr = float((yr_r > 0).sum()) / nd_yr * 100
    yr_mdd = float((yr_e / yr_e.cummax() - 1).min()) * 100
    # 当年持有标的
    yr_pos = pos.loc[yr_r.index].sum(axis=0)
    used = yr_pos[yr_pos > 0].sort_values(ascending=False)
    holds_str = " / ".join(["{} {:3.0f}%".format(POOL.get(c,c), p/yr_pos.sum()*100) for c, p in used.head(3).items()])
    
    line = "{:>6d}  {:>6d}  {:>8.1f}%  {:>8.1f}%  {:>7.1f}%  {:>5.1f}%  {:>7.1f}%  {}".format(
        yr, nd_yr, yr_cagr, yr_tot, yr_vol, yr_wr, yr_mdd, holds_str)
    print(line)

print("-" * 80)
line_all = "{:>6s}  {:>6d}  {:>8.1f}%  {:>8.1f}%  {:>7.1f}%  {:>5.1f}%  {:>7.1f}%  {}".format(
    "全部", nd, cagr, total_ret*100, np.sqrt(252)*float(ret.std())*100,
    float((ret>0).sum())/nd*100, mdd, "")
print(line_all)
print(sep)

print()
print("  全期关键指标:")
print("    年化 CAGR:  {:.1f}%".format(cagr))
print("    夏普比率:    {:.2f}".format(sharp))
print("    最大回撤:    {:.1f}%".format(mdd))
print("    总交易天数:  {}".format(nd))
print("    数据区间:    {} ~ {}".format(str(ret.index[0].strftime('%Y-%m-%d')),
                                           str(ret.index[-1].strftime('%Y-%m-%d'))))
print(sep)
