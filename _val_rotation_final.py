# -*- coding: utf-8 -*-
"""
宽基指数估值轮动策略
==================
核心理念：买最便宜的宽基指数，持有至正常估值卖出

数据：本地ETF历史（5只宽基：沪深300/中证500/中证1000/创业板指/科创50）
估值代理：滚动5年窗口 Price/MA12 乖离率的百分位
  - val_score = 1 - pct(price_to_ma)  →  越高越便宜

策略：
  A: 相对估值Top1（每月买最便宜的1只）
  B: 相对估值Top2（等权持有最便宜的2只）
  C: 低估过滤（val>0.7才买入）
  D: 动量Top1（基准对比）
  E: 估值+动量综合
  F: 低估+动量确认（估值低 AND 动量正）
  G: 低估+趋势确认（估值低 AND MA金叉）
  H: 三低估等权（分位<0.3才入场，否则持有）

回测区间：2018-02 至 2026-06（月频调仓）
基准：持有沪深300

对比目标：RSRS v4（年化21.5%, Sharpe 1.23, MDD -26.8%）
"""
import os, json, pandas as pd, numpy as np

np.random.seed(42)
OUT_DIR = r'D:\QClaw_Trading'
DATA = os.path.join(OUT_DIR, 'data', 'history')

# ===================== 1. 加载数据 =====================
etfs = {
    '510300': '沪深300',
    '510500': '中证500',
    '512100': '中证1000',
    '159915': '创业板指',
    '588080': '科创50',
}

all_data = {}
for code, name in etfs.items():
    path = os.path.join(DATA, f'{code}.json')
    with open(path, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    if isinstance(raw, list): df = pd.DataFrame(raw)
    elif 'data' in raw: df = pd.DataFrame(raw['data'])
    elif 'records' in raw: df = pd.DataFrame(raw['records'])
    else: continue
    dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
    cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
    if not dc or not cc: continue
    df['date'] = pd.to_datetime(df[dc])
    df['close'] = pd.to_numeric(df[cc], errors='coerce')
    df = df.dropna(subset=['date','close']).sort_values('date').reset_index(drop=True)
    df['ret'] = df['close'].pct_change()
    all_data[name] = df

print(f'加载 {len(all_data)} 个指数: {list(all_data.keys())}')

# ===================== 2. 月频聚合 =====================
def to_monthly(df, name):
    """日线 → 月线"""
    df2 = df.copy()
    df2['month'] = df2['date'].dt.to_period('M')
    monthly = df2.groupby('month').agg(
        close=('close', 'last'),
        ret=('ret', lambda x: (1+x).prod() - 1),
        open_=('close', 'first'),
    ).reset_index()
    monthly['date'] = monthly['month'].dt.to_timestamp()
    monthly = monthly.sort_values('date').reset_index(drop=True)
    return monthly[['date', 'close', 'ret', 'open_']]

monthly = {}
for name, df in all_data.items():
    m = to_monthly(df, name)
    # 计算因子
    m['ma12'] = m['close'].rolling(12, min_periods=6).mean()
    m['price_to_ma'] = m['close'] / m['ma12']  # <1=低于均线=偏便宜
    # 动量（12个月）
    m['mom12'] = m['ret'].rolling(12, min_periods=3).sum()
    # RSI(12)
    delta = m['close'].diff()
    gain = delta.clip(lower=0).rolling(12, min_periods=6).mean()
    loss = (-delta.clip(upper=0)).rolling(12, min_periods=6).mean()
    rs = gain / (loss + 1e-9)
    m['rsi12'] = 100 - (100 / (1 + rs))
    monthly[name] = m
    print(f'  {name}: {len(m)}月, {m["date"].min().date()}~{m["date"].max().date()}')

# ===================== 3. 估值分位 =====================
# 滚动60月（5年）窗口，计算price_to_ma的历史百分位
# val_score = 1 - pct  → 越高=越便宜
PCT_WINDOW = 60  # 5年窗口
MIN_PCT = 36     # 至少3年数据

for name in monthly:
    m = monthly[name].sort_values('date').copy()
    # val_score：price_to_ma的滚动5年百分位（越高=当前价格相对均线越低=越便宜）
    vals = m['price_to_ma'].values
    pct = np.full(len(vals), np.nan)
    for i in range(PCT_WINDOW, len(vals)):
        window = vals[max(0, i-PCT_WINDOW):i]
        valid = window[~np.isnan(window)]
        if len(valid) >= MIN_PCT:
            pct[i] = (valid > vals[i]).sum() / len(valid)  # >0.5=比历史一半时期便宜
    m['val_score'] = pct  # 0=最贵, 1=最便宜
    monthly[name] = m

# 科创50数据较短，用2年窗口
m = monthly['科创50'].copy()
vals = m['price_to_ma'].values
pct = np.full(len(vals), np.nan)
for i in range(24, len(vals)):
    window = vals[max(0, i-24):i]
    valid = window[~np.isnan(window)]
    if len(valid) >= 12:
        pct[i] = (valid > vals[i]).sum() / len(valid)
m['val_score'] = pct
monthly['科创50'] = m

# 对齐到共同月末
all_dates = set()
for df in monthly.values():
    all_dates.update(df['date'].tolist())
rebal_dates = sorted([d for d in all_dates if d >= pd.Timestamp('2018-06-01')])
print(f'\n调仓日: {len(rebal_dates)}个 ({rebal_dates[0].date()} ~ {rebal_dates[-1].date()})')

# ===================== 4. 回测引擎 =====================
def run_strat(name, fn_sel, fn_bench=None):
    """
    fn_sel(panel dict) -> [str] 选中的指数列表
    返回: dict{ann, mdd, sharpe, win, n}
    """
    hold_rets = []
    holdings = []
    current_hold = []
    
    for i, d in enumerate(rebal_dates[:-1]):
        next_d = rebal_dates[i+1]
        
        # 当日面板
        panel = {}
        for n, df in monthly.items():
            row = df[df['date'] == d]
            if not row.empty:
                panel[n] = row.iloc[0]
        
        if not panel:
            continue
        
        # 选股
        new_hold = fn_sel(panel)
        
        # 计算下期实际收益
        rets = []
        for idx_name in (current_hold if new_hold == current_hold else new_hold):
            df = monthly.get(idx_name)
            if df is None:
                continue
            nd_rows = df[df['date'] == next_d]
            if not nd_rows.empty:
                rets.append(nd_rows.iloc[0]['ret'])
        
        if rets:
            hold_rets.append({'date': next_d, 'ret': np.mean(rets)})
            holdings.append({'date': d, 'hold': list(current_hold)})
        
        current_hold = new_hold
    
    rd = pd.DataFrame(hold_rets).dropna().set_index('date')
    if rd.empty:
        return None
    
    cum = (1 + rd['ret']).cumprod()
    ann = cum.iloc[-1] ** (12.0 / len(cum)) - 1
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    sd = rd['ret'].std()
    sharpe = rd['ret'].mean() / sd * np.sqrt(12) if sd > 1e-10 else 0
    win = (rd['ret'] > 0).mean()
    
    return dict(name=name, ann=ann, mdd=mdd, sharpe=sharpe, win=win, n=len(rd),
                details=holdings)

# ===================== 5. 策略定义 =====================
# 各策略的选股函数
def s_val_top1(panel):
    """相对估值Top1"""
    valid = {k: v for k, v in panel.items() if not np.isnan(v.get('val_score', np.nan))}
    if not valid:
        return []
    return [max(valid, key=lambda k: valid[k]['val_score'])]

def s_val_top2(panel):
    """相对估值Top2"""
    valid = {k: v for k, v in panel.items() if not np.isnan(v.get('val_score', np.nan))}
    if not valid:
        return []
    return sorted(valid, key=lambda k: valid[k]['val_score'], reverse=True)[:2]

def s_val_low30_top1(panel):
    """低估过滤：val_score > 0.7（比历史上70%的时期便宜）"""
    valid = {k: v for k, v in panel.items() if v.get('val_score', 0) > 0.7}
    if not valid:
        return s_val_top1(panel)  # fallback
    return [max(valid, key=lambda k: valid[k]['val_score'])]

def s_val_low30_top2(panel):
    """低估过滤Top2"""
    valid = {k: v for k, v in panel.items() if v.get('val_score', 0) > 0.7}
    if not valid:
        return s_val_top2(panel)
    return sorted(valid, key=lambda k: valid[k]['val_score'], reverse=True)[:2]

def s_val_low30_top3(panel):
    """低估过滤Top3"""
    valid = {k: v for k, v in panel.items() if v.get('val_score', 0) > 0.7}
    if not valid:
        return s_val_top3(panel)
    return sorted(valid, key=lambda k: valid[k]['val_score'], reverse=True)[:3]

def s_val_top3(panel):
    return sorted(panel.keys(), key=lambda k: panel[k].get('val_score', 0), reverse=True)[:3]

def s_mom_top1(panel):
    """动量Top1（基准）"""
    valid = {k: v for k, v in panel.items() if not np.isnan(v.get('mom12', np.nan))}
    if not valid:
        return []
    return [max(valid, key=lambda k: valid[k]['mom12'])]

def s_val_mom(panel):
    """估值+动量综合：score = val_score * (1 + mom12)"""
    valid = {k: v for k, v in panel.items()
             if not np.isnan(v.get('val_score', np.nan))
             and not np.isnan(v.get('mom12', np.nan))}
    if not valid:
        return s_val_top1(panel)
    scored = {k: v['val_score'] * (1 + max(v['mom12'], 0)) for k, v in valid.items()}
    return [max(scored, key=lambda k: scored[k])]

def s_val_low30_mom_pos(panel):
    """低估(val>0.6) + 动量正"""
    valid = {k: v for k, v in panel.items()
             if v.get('val_score', 0) > 0.6
             and v.get('mom12', -999) > 0
             and not np.isnan(v.get('mom12', np.nan))}
    if not valid:
        # fallback: 只要低估就行
        valid = {k: v for k, v in panel.items() if v.get('val_score', 0) > 0.7}
    if not valid:
        return s_val_top1(panel)
    return sorted(valid, key=lambda k: valid[k]['val_score'], reverse=True)[:2]

def s_val_low50_top1(panel):
    """宽松低估过滤(val>0.5)"""
    valid = {k: v for k, v in panel.items() if v.get('val_score', 0) > 0.5}
    if not valid:
        return s_val_top1(panel)
    return [max(valid, key=lambda k: valid[k]['val_score'])]

def s_val_mom_blend(panel):
    """混合：val_score和mom12各占一半（截面标准化后）"""
    if not panel:
        return []
    vals = np.array([v.get('val_score', 0.5) for v in panel.values()])
    moms = np.array([v.get('mom12', 0) for v in panel.values()])
    # z-score
    vals_z = (vals - vals.mean()) / (vals.std() + 1e-9)
    moms_z = (moms - moms.mean()) / (moms.std() + 1e-9)
    scores = 0.5 * vals_z + 0.5 * moms_z
    names = list(panel.keys())
    best_i = np.argmax(scores)
    return [names[best_i]]

# ===================== 6. 运行 =====================
strats = [
    ('A_相对估值Top1',       s_val_top1),
    ('B_相对估值Top2',       s_val_top2),
    ('C_低估过滤Top1(val>0.7)', s_val_low30_top1),
    ('D_低估过滤Top2(val>0.7)', s_val_low30_top2),
    ('E_低估过滤Top3(val>0.7)', s_val_low30_top3),
    ('F_动量Top1',           s_mom_top1),
    ('G_估值+动量综合',       s_val_mom),
    ('H_低估+动量确认Top2',   s_val_low30_mom_pos),
    ('I_宽松低估Top1(>0.5)', s_val_low50_top1),
    ('J_估值动量混合Top1',    s_val_mom_blend),
]

results = []
for name, fn in strats:
    print(f'  {name}...', flush=True)
    r = run_strat(name, fn)
    if r:
        results.append(r)
        print(f'    {r["ann"]*100:.2f}% / {r["mdd"]*100:.2f}% / Sharpe={r["sharpe"]:.2f} / {r["win"]*100:.1f}% / {r["n"]}期')

# 基准
bench = monthly['沪深300'].copy()
bench = bench[bench['date'].isin(rebal_dates)].sort_values('date')
bench_cum = (1 + bench.set_index('date')['ret']).cumprod()
bann = bench_cum.iloc[-1] ** (12.0/len(bench_cum)) - 1
bpeak = bench_cum.cummax()
bmdd = ((bench_cum - bpeak)/bpeak).min()
bsharpe = bench['ret'].mean() / bench['ret'].std() * np.sqrt(12) if bench['ret'].std() > 1e-10 else 0
results.append(dict(name='沪深300基准', ann=bann, mdd=bmdd, sharpe=bsharpe, win=0, n=len(bench)))

# ===================== 7. 打印 =====================
print('\n' + '='*65)
print('宽基指数估值轮动策略 — 回测结果')
print('='*65)
print(f"{'策略':<28}{'年化':>9}{'MDD':>9}{'Sharpe':>8}{'胜率':>7}{'期数':>5}")
print('-'*65)
for r in sorted(results, key=lambda x: x['sharpe'], reverse=True):
    print(f"{r['name']:<28}{r['ann']*100:>8.2f}%{r['mdd']*100:>8.2f}%{r['sharpe']:>7.2f}  {r['win']*100:>5.1f}% {r['n']:>4d}")

print()
valid = sorted(results, key=lambda x: x['sharpe'], reverse=True)
if valid:
    best = valid[0]
    print(f'★ 最佳: {best["name"]}  年化={best["ann"]*100:.2f}%  Sharpe={best["sharpe"]:.2f}  MDD={best["mdd"]*100:.2f}%')

# ===================== 8. 年度明细 =====================
def get_annual(name_str, fn):
    """获取年度收益"""
    rets_by_yr = {}
    for i, d in enumerate(rebal_dates[:-1]):
        nd = rebal_dates[i+1]
        panel = {n: df[df['date']==d].iloc[0] for n, df in monthly.items() if not df[df['date']==d].empty}
        if not panel: continue
        hold = fn(panel)
        yr = pd.Timestamp(nd).year
        rets_list = []
        for idx in hold:
            nd_df = monthly[idx]
            nd_row = nd_df[nd_df['date']==nd]
            if not nd_row.empty:
                rets_list.append(nd_row.iloc[0]['ret'])
        if rets_list:
            rets_by_yr.setdefault(yr, []).append(np.mean(rets_list))
    
    if not rets_by_yr:
        return {}
    annual = {}
    for yr, rets in sorted(rets_by_yr.items()):
        annual[yr] = np.mean(rets) if rets else 0
    return annual

# 年度明细（最佳策略 + 基准）
best_fn_map = {name: fn for name, fn in strats}
print('\n--- 年度收益对比 ---')
for top_n in range(min(3, len(valid))):
    r = valid[top_n]
    fn = best_fn_map.get(r['name'])
    if fn:
        ann = get_annual(r['name'], fn)
        print(f'\n  [{r["name"]}] Sharpe={r["sharpe"]:.2f}')
        for yr in sorted(ann.keys()):
            print(f'    {yr}: {ann[yr]*100:+.1f}%')

# 基准年度
print(f'\n  [沪深300基准]')
for yr, ret in bench.set_index('date').groupby(bench['date'].dt.year)['ret'].apply(lambda x: (1+x).prod()-1).items():
    print(f'    {yr}: {ret*100:+.1f}%')

# ===================== 9. 估值分位现状 =====================
print('\n--- 当前估值分位（2026年6月末）---')
for name in monthly:
    df = monthly[name]
    last = df[df['date'].notna()].iloc[-1]
    print(f'  {name}: val_score={last["val_score"]:.3f}  price_to_ma={last["price_to_ma"]:.3f}  乖离={((last["price_to_ma"]-1)*100):+.1f}%  val>{0.7:"是" if last["val_score"]>0.7 else "否"}')

# 保存
res_df = pd.DataFrame(results)
res_df.to_csv(os.path.join(OUT_DIR, 'val_rotation_results.csv'), index=False)

# 保存各指数月线数据
for name, df in monthly.items():
    df.to_csv(os.path.join(OUT_DIR, 'data', 'index_val', f'{name}.csv'), index=False)

print(f'\n结果已保存: {OUT_DIR}/val_rotation_results.csv')
print(f'指数数据已保存: {OUT_DIR}/data/index_val/')
