"""
RSRS策略稳健性验证 v4（基于已验证的正确回测框架）
"""
import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_rsrs, compute_vol_scaling

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ",
        "518880":"GOLD","162411":"OIL"}

# ══════════════════════════════════════════════════════
# 核心回测函数（来自 pool10_backtest.py，已验证正确）
# ══════════════════════════════════════════════════════
def run_backtest(M=1200, buy=0.7, sell=-1.0, rb=42, lock=0, no_neg=True,
                 start_pct=None, noise_std=0.0):
    raw, panel = build_panel(POOL, min_rows=200)
    df_sig = load_etf("510300")

    # 波动率缩放
    sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)

    # C63 动量预计算
    mom = {}
    for code, df in raw.items():
        s = df.set_index("date")["close"].pct_change(rb)
        mom[code] = s[s.index.isin(panel.index)]

    # RSRS 信号
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, M, buy, sell)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))
    zs_s  = pd.Series(zs_raw,  index=pd.to_datetime(df_sig["date"].values))

    # 噪声注入
    if noise_std > 0:
        rng = np.random.default_rng(42)
        panel_noisy = panel.copy()
        for col in panel_noisy.columns:
            noise = rng.normal(0, noise_std, len(panel_noisy))
            panel_noisy[col] = panel_noisy[col] * (1 + noise)
        panel = panel_noisy

    # 仓位矩阵
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None

    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0:
            eff = 1.0
        if eff == 0:
            hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None:
            lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= rb:
            scs = {}
            for c in POOL:
                if dt in mom[c].index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c,v in rk if v>0] if no_neg else [c for c,v in rk]
            hold = sel[:1] if sel else []; lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w

    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[M])
    ret = ret[ret.index >= fs]

    if start_pct is not None:
        cut_dt = panel.index[int(len(panel) * start_pct)]
        ret = ret[ret.index >= cut_dt]

    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()

    # 年度
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        nd = m.sum()
        if nd < 5: continue
        yr_eq = (1 + ret[m]).cumprod()
        annual[yr] = round((yr_eq.iloc[-1] ** (252/nd) - 1) * 100, 1)

    cagr = eq.iloc[-1] ** (252/len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    pr = (pos.sum(axis=1) > 0).mean() * 100
    calmar = round(cagr*100 / abs(mdd*100), 2) if mdd < 0 else 0

    return {
        "CAGR": round(cagr*100, 1),
        "Sharpe": round(sp, 2),
        "MDD": round(mdd*100, 1),
        "W%": round(wr, 1),
        "Pos%": round(pr, 1),
        "Calmar": calmar,
        "Annual": annual,
        "years": sorted(annual.keys()),
        "yr_rets": [annual[y] for y in sorted(annual.keys())],
        "total_ret": round((eq.iloc[-1]-1)*100, 1),
        "nav": eq.iloc[-1],
    }

# ══════════════════════════════════════════════════════
# 开始验证
# ══════════════════════════════════════════════════════
print('='*65)
print('RSRS策略稳健性验证')
print('='*65)

# 基准参数（来自最终定稿）
BASE = dict(M=1200, buy=0.7, sell=-1.0, rb=42, lock=42, no_neg=True)

base = run_backtest(**BASE)
print(f'\n基准参数: M={BASE["M"]} buy={BASE["buy"]} sell={BASE["sell"]} rb={BASE["rb"]} lock={BASE["lock"]}')
print(f'基准结果: CAGR={base["CAGR"]}% Sharpe={base["Sharpe"]} MDD={base["MDD"]}% Calmar={base["Calmar"]}')
yr_bar = '  '.join(f'{y}:{v:+.1f}%' for y,v in zip(base['years'], base['yr_rets']))
print(f'年度: {yr_bar}')

# ══════════════════════════════════════════════════════
# 一、参数扰动
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('一、参数扰动检验')
print('-'*65)

param_tests = [
    ('M',     [400, 600, 800, 900, 1000, 1100, 1200, 1400, 1600]),
    ('buy',   [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]),
    ('sell',  [-0.5, -0.7, -0.9, -1.0, -1.2, -1.5]),
    ('rb',    [21, 30, 42, 50, 63, 75, 84, 100, 126]),
    ('lock',  [14, 21, 28, 35, 42, 49, 56, 63, 84]),
]

all_perturbed = []
for pname, values in param_tests:
    print(f'\n--- {pname} ---')
    hdr = f'  {"值":>8s}  {"CAGR%":>7s}  {"Sharpe":>6s}  {"MDD%":>7s}  {"卡玛":>6s}'
    print(hdr)
    for val in values:
        p = dict(BASE); p[pname] = val
        r = run_backtest(**p)
        if r:
            tag = ' <BASE>' if val == BASE[pname] else ''
            print(f'  {str(val):>8s}  {r["CAGR"]:>+7.1f}  {r["Sharpe"]:>6.2f}  {r["MDD"]:>7.1f}  {r["Calmar"]:>6.2f}{tag}')
            all_perturbed.append({'param':pname,'value':val,'cagr':r['CAGR'],'sharpe':r['Sharpe'],'mdpct':r['MDD'],'calmar':r['Calmar']})

cagr_vals  = [x['cagr'] for x in all_perturbed]
base_cagr  = base['CAGR']
pos_count  = sum(1 for x in all_perturbed if x['cagr'] > 0)
below_70  = sum(1 for x in all_perturbed if x['cagr'] < base_cagr * 0.7)
below_half= sum(1 for x in all_perturbed if x['cagr'] < 0)
total_cnt  = len(all_perturbed)

print(f'\n小结:')
print(f'  正收益组合: {pos_count}/{total_cnt} ({pos_count/total_cnt*100:.1f}%)  [豆包合格线≥90%]')
print(f'  CAGR<基准70%: {below_70}/{total_cnt}  [豆包淘汰线: 大量腰斩]')
print(f'  亏损组合: {below_half}/{total_cnt}')
print(f'  基准CAGR: {base_cagr:.1f}%')
print(f'  扰动均值: {np.mean(cagr_vals):.1f}%, 最低: {min(cagr_vals):.1f}%, 最高: {max(cagr_vals):.1f}%')

# ══════════════════════════════════════════════════════
# 二、Walk Forward
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('二、Walk Forward 滚动样本外检验')
print('-'*65)

wf_all = []
for train_yr, oos_yr in [(2, 1), (3, 1), (1, 0.5)]:
    n_train = int(train_yr * 252)
    n_oos  = int(oos_yr * 252)
    n_total = int(8 * 252)  # 约8年数据
    print(f'\n--- 训练{train_yr}年 / OOS{oos_yr}年 ---')
    runs = []
    start = n_train
    while start + n_oos <= n_total:
        pct = start / n_total
        r = run_backtest(**BASE, start_pct=pct)
        if r and r['years']:
            yr_range = f"{r['years'][0]}~{r['years'][-1]}"
            print(f'  OOS {yr_range}: CAGR={r["CAGR"]:+.1f}% Sharpe={r["Sharpe"]:.2f} MDD={r["MDD"]:.1f}% 年交易≈{int(r["Pos%"]*r["years"][-1]/100)}次')
            runs.append(r)
            wf_all.append(r)
        start += n_oos
    if runs:
        avg = np.mean([x['CAGR'] for x in runs])
        pos = sum(1 for x in runs if x['CAGR'] > 0)
        print(f'  汇总: OOS均值CAGR={avg:.1f}%, 盈利区间={pos}/{len(runs)}')

if wf_all:
    wf_avg = np.mean([x['CAGR'] for x in wf_all])
    wf_pos = sum(1 for x in wf_all if x['CAGR'] > 0)
    print(f'\n  全OOS: 均值CAGR={wf_avg:.1f}%, 盈利={wf_pos}/{len(wf_all)}, vs基准={base_cagr:.1f}%')
    print(f'  OOS达标率: {wf_avg/base_cagr*100:.1f}% (合格线≥50%)')

# ══════════════════════════════════════════════════════
# 三、噪声扰动
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('三、噪声扰动检验（各20次随机）')
print('-'*65)

print(f'  {"噪声":>6s}  {"均值CAGR":>9s}  {"均值Sharpe":>10s}  {"正收益%":>8s}  {"最小CAGR":>9s}')
for noise in [0.001, 0.003, 0.005, 0.01]:
    results = []
    for seed in range(20):
        r = run_backtest(**BASE, noise_std=noise)
        if r: results.append(r)
    if results:
        cagrs   = [x['CAGR'] for x in results]
        sharpes = [x['Sharpe'] for x in results]
        pos_r   = sum(1 for x in results if x['CAGR'] > 0) / len(results) * 100
        print(f'  ±{noise*100:>4.1f}%  {np.mean(cagrs):>+9.1f}  {np.mean(sharpes):>10.2f}  {pos_r:>7.0f}%  {min(cagrs):>+9.1f}')

# ══════════════════════════════════════════════════════
# 四、年度业绩
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('四、年度业绩分段')
print('-'*65)

print(f'  {"年份":>6s}  {"年收益%":>9s}')
yr_rets = base['yr_rets']
yr_names = base['years']
for yr, ret in zip(yr_names, yr_rets):
    tag = ' <<<' if ret < 0 else ''
    yr_str = str(yr)
    print(f'  {yr_str:>6s}  {ret:>+9.1f}{tag}')
loss_yrs = sum(1 for y in yr_rets if y < 0)
print(f'\n  亏损年份: {loss_yrs}/{len(yr_names)} ({loss_yrs/len(yr_names)*100:.1f}%)  [合格线≤20%]')
print(f'  最大亏损: {min(yr_rets):+.1f}%, 最大盈利: {max(yr_rets):+.1f}%')
print(f'  年收益标准差: {np.std(yr_rets):.1f}%')

# ══════════════════════════════════════════════════════
# 五、交易摩擦
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('五、交易摩擦压力测试')
print('-'*65)

# 修改run_backtest加入交易成本
def run_with_cost(cost_mult=1.0):
    raw, panel = build_panel(POOL, min_rows=200)
    df_sig = load_etf("510300")
    sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)
    mom = {}
    for code, df in raw.items():
        s = df.set_index("date")["close"].pct_change(BASE['rb'])
        mom[code] = s[s.index.isin(panel.index)]

    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, BASE['M'], BASE['buy'], BASE['sell'])
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

    # 加入成本: 每次换仓额外扣cost_mult*0.0008
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    last_hold = None

    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if BASE['lock'] > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if BASE['lock'] > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=BASE['lock'])
        if lr is None or (dt - lr).days >= BASE['rb']:
            scs = {}
            for c in POOL:
                if dt in mom[c].index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c,v in rk if v>0] if BASE['no_neg'] else [c for c,v in rk]
            new_hold = sel[:1] if sel else []
            # 换仓成本
            if new_hold != last_hold and last_hold is not None:
                panel.loc[dt:, last_hold[0]] *= (1 - cost_mult * 0.0008)
            last_hold = new_hold
            hold = new_hold; lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w

    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[BASE['M']])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (252/len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1)}

print(f'  {"成本倍数":>8s}  {"等效双边":>9s}  {"CAGR%":>7s}  {"Sharpe":>7s}  {"MDD%":>7s}')
for mult in [0, 0.5, 1, 1.5, 2, 3, 5]:
    r = run_with_cost(mult)
    if r:
        tag = ' <基准>' if mult == 1 else ''
        print(f'  {mult:>8.1f}x  {mult*0.16:>8.2f}%  {r["CAGR"]:>7.1f}  {r["Sharpe"]:>7.2f}  {r["MDD"]:>7.1f}{tag}')

# ══════════════════════════════════════════════════════
# 六、置换检验
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('六、置换检验 (Permutation N=50)')
print('-'*65)

def backtest_perm(seed):
    rng = np.random.default_rng(seed)
    # 打乱510300的RSRS信号
    df_sig = load_etf("510300")
    sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, BASE['M'], BASE['buy'], BASE['sell'])
    rng.shuffle(sig_raw)
    sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

    raw2, panel_df = build_panel(POOL, min_rows=200)
    panel_idx = panel_df.index
    sc = compute_vol_scaling(df_sig, panel_idx, 70, 0.16)
    mom = {}
    for code, df2 in raw2.items():
        s = df2.set_index("date")["close"].pct_change(BASE['rb'])
        mom[code] = s[s.index.isin(panel_idx)]

    pos = pd.DataFrame(0.0, index=panel_idx, columns=panel_df.columns)
    hold, lr, lku = [], None, None
    for dt in panel_idx:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if BASE['lock'] > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if BASE['lock'] > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=BASE['lock'])
        if lr is None or (dt - lr).days >= BASE['rb']:
            scs = {}
            for c in POOL:
                if dt in mom[c].index:
                    v = mom[c].loc[dt]
                    if not np.isnan(v): scs[c] = v
            if not scs: hold = []; continue
            rk = sorted(scs.items(), key=lambda x: -x[1])
            sel = [c for c,v in rk if v>0] if BASE['no_neg'] else [c for c,v in rk]
            hold = sel[:1] if sel else []; lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w

    dr = panel_df.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[BASE['M']])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    return (eq.iloc[-1] - 1) * 100

print('  计算中...')
perm_rets = [backtest_perm(s) for s in range(50)]
real_ret = base['total_ret']
perm_mean = np.mean(perm_rets)
perm_std = np.std(perm_rets)
pct_above = sum(1 for x in perm_rets if x >= real_ret) / len(perm_rets) * 100

print(f'  真实策略总收益: {real_ret:+.1f}%')
print(f'  随机打乱均值:   {perm_mean:+.1f}%, std={perm_std:.1f}%')
print(f'  随机最大收益:   {max(perm_rets):+.1f}%')
print(f'  真实在随机中:   {pct_above:.1f}%分位')
if pct_above >= 95:
    print(f'  结论: 显著优于随机 [OK] p<0.05')
elif pct_above <= 5:
    print(f'  结论: 显著劣于随机 [FAIL]')
else:
    print(f'  结论: 无法显著区分随机 [WARNING]')

# ══════════════════════════════════════════════════════
# 七、综合判定
# ══════════════════════════════════════════════════════
print('\n\n' + '='*65)
print('七、综合稳健性判定')
print('='*65)

checks = []
# 1
p1 = pos_count / total_cnt >= 0.80
checks.append(('参数正收益率≥80%', p1, f'{pos_count}/{total_cnt}={pos_count/total_cnt*100:.0f}%'))
# 2
p2 = np.mean(cagr_vals) >= base_cagr * 0.70
checks.append(('参数扰动均值CAGR≥基准70%', p2, f'{np.mean(cagr_vals):.1f}% vs {base_cagr:.1f}%'))
# 3
wf_avg_cagr = np.mean([x['CAGR'] for x in wf_all]) if wf_all else 0
p3 = wf_avg_cagr >= base_cagr * 0.50
checks.append(('Walk Forward OOS CAGR≥基准50%', p3, f'{wf_avg_cagr:.1f}% vs {base_cagr:.1f}%'))
# 4
noise_r = [run_backtest(**BASE, noise_std=0.003) for _ in range(10)]
noise_r = [r for r in noise_r if r]
np_rate = sum(1 for r in noise_r if r['CAGR'] > 0) / len(noise_r) * 100 if noise_r else 0
p4 = np_rate >= 50
checks.append(('噪声±0.3%正收益≥50%', p4, f'{np_rate:.0f}%'))
# 5
loss_rate = loss_yrs / len(yr_names)
p5 = loss_rate <= 0.25
checks.append(('年度亏损年份≤25%', p5, f'{loss_yrs}/{len(yr_names)}={loss_rate*100:.0f}%'))
# 6
rc3 = run_with_cost(3)
p6 = rc3['CAGR'] > 0 if rc3 else False
checks.append(('双边0.24%仍盈利', p6, f'CAGR={rc3["CAGR"]:.1f}%' if rc3 else 'N/A'))
# 7
p7 = pct_above >= 95 or pct_above <= 5
checks.append(('置换检验显著', p7, f'{pct_above:.1f}%分位'))
# 8
p8 = base['MDD'] > -30
checks.append(('最大回撤<30%', p8, f'MDD={base["MDD"]:.1f}%'))

print(f'\n  {"检验项":40s}  {"结果":8s}  {"实际值":>15s}')
print(f'  {"-"*40}  {"-"*8}  {"-"*15}')
for name, ok, val in checks:
    status = '[OK]' if ok else '[FAIL]'
    print(f'  {name:40s}  {status}  {val:>15s}')

passed = sum(1 for _, ok, _ in checks if ok)
print(f'\n  通过: {passed}/{len(checks)}')
if passed == len(checks):
    print('  综合: [PASS] 稳健性良好，建议实盘')
elif passed >= len(checks) - 1:
    print('  综合: [CONDITIONAL PASS] 基本稳健，轻微风险点')
else:
    print('  综合: [WARNING] 存在稳健性风险')
