# -*- coding: utf-8 -*-
"""
ETF板块动量+估值轮动 — 正确版本
关键：动量是信号，下期收益是实际持仓收益
"""
import os, json, pandas as pd, numpy as np

np.random.seed(42)
HIST_DIR = r'D:\QClaw_Trading\data\history'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUT = r'D:\QClaw_Trading\etf_val_real_results.csv'

# ====================== 1. 加载 ======================
with open(POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)

code_to_cat = {i['code'].strip(): (i.get('category') or '其他').strip() or '其他'
                for i in pool['data']}

def read_etf(path):
    with open(path, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    if isinstance(raw, list): df = pd.DataFrame(raw)
    elif isinstance(raw, dict):
        if 'data' in raw: df = pd.DataFrame(raw['data'])
        elif 'records' in raw: df = pd.DataFrame(raw['records'])
        else: df = pd.DataFrame([raw])
    else: return pd.DataFrame()
    dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
    cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
    hc = next((c for c in df.columns if c.lower() in ['high','h']), None)
    lc = next((c for c in df.columns if c.lower() in ['low','l']), None)
    vc = next((c for c in df.columns if c.lower() in ['volume','v']), None)
    if not dc or not cc: return pd.DataFrame()
    out = pd.DataFrame()
    out['date'] = pd.to_datetime(df[dc], errors='coerce')
    out['close'] = pd.to_numeric(df[cc], errors='coerce')
    out['high'] = pd.to_numeric(df[hc], errors='coerce') if hc else np.nan
    out['low'] = pd.to_numeric(df[lc], errors='coerce') if lc else np.nan
    out['volume'] = pd.to_numeric(df[vc], errors='coerce') if vc else np.nan
    return out

etf_list = []
for f in sorted(os.listdir(HIST_DIR)):
    if not f.endswith('.json'): continue
    code = f[:-5]
    df = read_etf(os.path.join(HIST_DIR, f))
    if df.empty: continue
    df['code'] = code
    df['category'] = code_to_cat.get(code, '其他')
    etf_list.append(df)

etf_df = pd.concat(etf_list, ignore_index=True)
etf_df = etf_df.dropna(subset=['close', 'date'])
etf_df = etf_df[etf_df['category'] != '其他']
etf_df = etf_df.sort_values(['code', 'date'])
print(f'ETF: {etf_df["code"].nunique()}只, {len(etf_df)}行')

# ====================== 2. 单ETF因子 ======================
etf_df = etf_df.sort_values(['code', 'date'])
etf_df['ret'] = etf_df.groupby('code')['close'].pct_change()          # 日收益率
etf_df['atr'] = (etf_df['high'] - etf_df['low']) / etf_df.groupby('code')['close'].shift(1)
etf_df['atr14'] = etf_df.groupby('code')['atr'].transform(lambda x: x.ewm(span=14, min_periods=5).mean())
etf_df['atr60'] = etf_df.groupby('code')['atr'].transform(lambda x: x.ewm(span=60, min_periods=15).mean())
etf_df['atr_ratio'] = etf_df['atr14'] / etf_df['atr60']
# 12天动量（用于截面排名）
etf_df['mom12'] = etf_df.groupby('code')['ret'].transform(lambda x: x.rolling(12, min_periods=6).sum())
# 成交量rank代理
etf_df['vol_mean20'] = etf_df.groupby('code')['volume'].transform(lambda x: x.rolling(20, min_periods=10).mean())
etf_df['vol_ratio'] = etf_df['volume'] / etf_df['vol_mean20']

etf_df = etf_df.dropna(subset=['ret', 'mom12'])
etf_df = etf_df[etf_df['date'] >= '2020-01-01']
etf_df = etf_df[etf_df['date'] <= '2026-07-10']
print(f'有效: {etf_df["code"].nunique()}只, {len(etf_df)}行')

# ====================== 3. 板块日线聚合 ======================
agg = etf_df.groupby(['date', 'category']).agg(
    avg_ret=('ret', 'mean'),
    mom12=('mom12', 'mean'),
    atr_ratio=('atr_ratio', 'mean'),
    vol_ratio=('vol_ratio', 'mean'),
    n_etfs=('code', 'count'),
).reset_index().rename(columns={'category': 'sector'})
agg = agg.sort_values(['sector', 'date'])
agg = agg[agg['n_etfs'] >= 2]  # 至少2只ETF

# 截面归一化
agg['mom_z'] = agg.groupby('date')['mom12'].transform(lambda x: (x - x.mean()) / (x.std() + 1e-9))
agg['atr_z'] = agg.groupby('date')['atr_ratio'].transform(lambda x: (x - x.mean()) / (x.std() + 1e-9))
# 估值代理（成交量缩=低估）
agg['val_score'] = agg.groupby('date')['vol_ratio'].rank(pct=True).transform(lambda x: 1 - x)

dates = sorted(agg['date'].unique())
print(f'板块日线: {len(agg)}行, {len(dates)}天, {agg["sector"].nunique()}板块')

# ====================== 4. 正确回测 ======================
# 逻辑：T日用因子选板块 → 记录T日收盘后换仓 → T+1日收益为持仓收益
# 由于我们用收盘价算因子，下期收益 = 下一天板块日均收益

results = []

def run_strat(name, note, score_fn, score_col='score'):
    """
    score_fn(day_df) -> DataFrame with score column
    持仓收益 = 下一天实际avg_ret（避免使用当天数据）
    """
    hold_rets = []   # 每持有期（日）收益
    daily_rets = []  # 按自然日
    last_sel = None
    
    for i, d in enumerate(dates[:-1]):
        today = agg[agg['date'] == d]
        next_day = agg[agg['date'] == dates[i+1]]
        
        # 用因子选板块
        scored = score_fn(today.copy())
        if scored.empty: continue
        
        top_sector = scored.iloc[0]['sector']
        
        # 获取下一天该板块的实际收益
        nd_sec = next_day[next_day['sector'] == top_sector]
        if nd_sec.empty: continue
        
        r = nd_sec.iloc[0]['avg_ret']
        hold_rets.append({'date': dates[i+1], 'ret': r})
    
    if not hold_rets:
        print(f'{name}: 无有效持仓记录')
        return None
    rd = pd.DataFrame(hold_rets)
    if 'date' not in rd.columns or rd.empty:
        print(f'{name}: 无有效数据')
        return None
    rd = rd.dropna(subset=['ret']).set_index('date')
    if rd.empty: return None
    
    cum = (1 + rd['ret']).cumprod()
    ann = cum.iloc[-1] ** (252.0 / len(rd)) - 1
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    sd = rd['ret'].std()
    sharpe = rd['ret'].mean() / sd * np.sqrt(252) if sd > 1e-10 else 0
    win = (rd['ret'] > 0).mean()
    return dict(strategy=name, note=note, ann=ann, mdd=mdd, sharpe=sharpe, win=win, n=len(rd))

# 策略定义
strats = [
    ('A_纯动量TOP1',       '12天动量截面最强',
        lambda d: d.dropna(subset=['mom12']).assign(score=d['mom12']).nlargest(1,'score')),
    ('B_低估值动量TOP1',   'val_score>0.5中选动量最强',
        lambda d: (d.dropna(subset=['mom12','val_score'])
                   .assign(score=d.apply(lambda r: r['mom12'] if r['val_score']>0.5 else -999, axis=1))
                   .nlargest(1,'score')) if len(d[d['val_score']>0.5])>0 
                   else d.dropna(subset=['mom12']).assign(score=d['mom12']).nlargest(1,'score')),
    ('C_估值加权动量TOP1', '动量分×(1-val_score)',
        lambda d: d.dropna(subset=['mom12','val_score']).assign(score=d['mom12']*(1-d['val_score'])).nlargest(1,'score')),
    ('D_纯低估TOP1',       'val_score最高(量缩最少)',
        lambda d: d.dropna(subset=['val_score']).nlargest(1,'val_score')),
    ('E_动量+ATR>0.9',    'ATR过滤假突破',
        lambda d: (d.dropna(subset=['mom12','atr_ratio'])
                    .assign(score=d.apply(lambda r: r['mom12'] if r['atr_ratio']>0.9 else -999, axis=1))
                    .nlargest(1,'score')) if len(d[d['atr_ratio']>0.9])>0
                    else d.dropna(subset=['mom12']).assign(score=d['mom12']).nlargest(1,'score')),
    ('F_三维因子',         'mom×atr×(1-val)',
        lambda d: d.dropna(subset=['mom12','atr_ratio','val_score']).assign(score=d['mom12']*d['atr_ratio']*(1-d['val_score'])).nlargest(1,'score')),
    ('G_动量ATR双因子',    '(mom_z+atr_z)/2',
        lambda d: d.dropna(subset=['mom_z','atr_z']).assign(score=(d['mom_z']+d['atr_z'])/2).nlargest(1,'score')),
]

for name, note, fn in strats:
    r = run_strat(name, note, fn)
    if r: results.append(r)

# 基准
bench = agg.groupby('date')['avg_ret'].mean()
bench_cum = (1+bench).cumprod()
bench_ann = bench_cum.iloc[-1] ** (252.0/len(bench)) - 1
bench_peak = bench_cum.cummax()
bench_mdd = ((bench_cum-bench_peak)/bench_peak).min()
bench_sharpe = bench.mean()/bench.std()*np.sqrt(252) if bench.std()>1e-10 else 0

# 打印
print('\n================ 回测结果 ================')
hdr = f"{'策略':<22}{'年化':>9}{'MDD':>9}{'Sharpe':>8}{'胜率':>7}{'交易天数':>6}"
print(hdr)
for r in sorted(results, key=lambda x: x['sharpe'], reverse=True):
    print(f"{r['strategy']:<22}{r['ann']*100:>8.2f}%{r['mdd']*100:>8.2f}%{r['sharpe']:>7.2f}  {r['win']*100:>5.1f}%  {r['n']:>5d}")
print(f"{'等权持有基准':<22}{bench_ann*100:>8.2f}%{bench_mdd*100:>8.2f}%{bench_sharpe:>7.2f}  {'--':>5}  {len(bench):>5d}")

# 最佳策略年度明细
valid = sorted(results, key=lambda x: x['sharpe'], reverse=True)
if valid:
    best = valid[0]
    print(f"\n★ 最佳: {best['strategy']} Sharpe={best['sharpe']:.2f}")
    
    # 重建最佳策略收益
    best_name = best['strategy']
    fn_map = {s[0]: s[2] for s in strats}
    if best_name in fn_map:
        fn = fn_map[best_name]
        yr_rets = []
        for i, d in enumerate(dates[:-1]):
            today = agg[agg['date']==d]
            nd = agg[agg['date']==dates[i+1]]
            scored = fn(today)
            if scored.empty: continue
            sec = scored.iloc[0]['sector']
            nd_sec = nd[nd['sector']==sec]
            if nd_sec.empty: continue
            yr_rets.append({'date':dates[i+1],'ret':nd_sec.iloc[0]['avg_ret'],'yr':pd.Timestamp(dates[i+1]).year})
        yr_df = pd.DataFrame(yr_rets).dropna()
        if not yr_df.empty:
            print('\n--- 年度收益明细 ---')
            bench_by_yr = agg.copy()
            bench_by_yr['yr'] = bench_by_yr['date'].dt.year
            for yr in sorted(yr_df['yr'].unique()):
                grp = yr_df[yr_df['yr']==yr]
                bc = bench_by_yr[bench_by_yr['yr']==yr].groupby('date')['avg_ret'].mean()
                strat_cum = (1+grp.set_index('date')['ret']).prod() if not grp.empty else 1
                bench_cum_yr = (1+bc).prod()
                excess = strat_cum / bench_cum_yr - 1
                print(f'  {yr}: 策略={(strat_cum-1)*100:+.1f}% 基准={(bench_cum_yr-1)*100:+.1f}% 超额={excess*100:+.1f}% ({len(grp)}天)')

res_df = pd.DataFrame(results).sort_values('sharpe', ascending=False)
res_df.to_csv(OUT, index=False)
print(f'\n结果已保存: {OUT}')
