# -*- coding: utf-8 -*-
"""
ETF板块动量+估值轮动策略回测（修复版）
- 正确聚合：先算单ETF日收益，再等权平均到板块
- 估值：用成交量rank代理低估板块
- 对比策略A/B/C/D/E
"""
import os, json, pandas as pd, numpy as np

np.random.seed(42)
HIST_DIR = r'D:\QClaw_Trading\data\history'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUT = r'D:\QClaw_Trading\etf_val_real_results.csv'

# ====================== 1. 加载ETF池 ======================
with open(POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)

code_to_cat = {i['code'].strip(): (i.get('category') or '其他').strip() or '其他'
                for i in pool['data']}

# 读取本地历史ETF
files = sorted([f for f in os.listdir(HIST_DIR) if f.endswith('.json')])
etf_list = []
for f in files:
    code = f[:-5]
    try:
        with open(os.path.join(HIST_DIR, f), 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        if isinstance(raw, list) and len(raw) > 0:
            df = pd.DataFrame(raw)
        elif isinstance(raw, dict) and 'data' in raw:
            df = pd.DataFrame(raw['data'])
        else:
            df = pd.DataFrame(raw)
        df['code'] = code
        etf_list.append(df)
    except:
        pass

etf_df = pd.concat(etf_list, ignore_index=True)

# 标准化字段
date_col = 'date' if 'date' in etf_df.columns else 'day'
etf_df['date'] = pd.to_datetime(etf_df[date_col])
close_col = 'close' if 'close' in etf_df.columns else ('p' if 'p' in etf_df.columns else None)
vol_col = 'volume' if 'volume' in etf_df.columns else ('v' if 'v' in etf_df.columns else None)
high_col = 'high' if 'high' in etf_df.columns else ('h' if 'h' in etf_df.columns else None)
low_col = 'low' if 'low' in etf_df.columns else ('l' if 'l' in etf_df.columns else None)

etf_df['close'] = pd.to_numeric(etf_df[close_col], errors='coerce')
etf_df['volume'] = pd.to_numeric(etf_df[vol_col], errors='coerce') if vol_col else np.nan
etf_df['high'] = pd.to_numeric(etf_df[high_col], errors='coerce') if high_col else np.nan
etf_df['low'] = pd.to_numeric(etf_df[low_col], errors='coerce') if low_col else np.nan
etf_df['category'] = etf_df['code'].map(code_to_cat).fillna('其他')

etf_df = etf_df.dropna(subset=['close', 'date'])
etf_df = etf_df.sort_values(['code', 'date'])
etf_df = etf_df[etf_df['category'] != '其他']

print(f'有效ETF: {etf_df["code"].nunique()}只, {len(etf_df)}行')
print(f'板块: {sorted(etf_df["category"].unique())}')

# ====================== 2. 正确聚合：单ETF收益 → 板块等权 ======================
# 先算单ETF日收益率
etf_df = etf_df.sort_values(['code', 'date'])
etf_df['ret'] = etf_df.groupby('code')['close'].pct_change()

# ATR
if 'high' in etf_df.columns and 'low' in etf_df.columns:
    etf_df['atr'] = (etf_df['high'] - etf_df['low']) / etf_df.groupby('code')['close'].shift(1)
    etf_df['atr14'] = etf_df.groupby('code')['atr'].transform(lambda x: x.ewm(span=14, min_periods=7).mean())
    etf_df['atr60'] = etf_df.groupby('code')['atr'].transform(lambda x: x.ewm(span=60, min_periods=20).mean())
    etf_df['atr_ratio'] = etf_df['atr14'] / etf_df['atr60']
else:
    etf_df['atr_ratio'] = 1.0

# 动量（12天累积）
etf_df['mom12'] = etf_df.groupby('code')['ret'].transform(lambda x: x.rolling(12, min_periods=6).sum())

# 12天滚动ATR
etf_df['vol_mean20'] = etf_df.groupby('code')['volume'].transform(lambda x: x.rolling(20, min_periods=10).mean())
etf_df['vol_ratio'] = etf_df['volume'] / etf_df['vol_mean20']

# 过滤有效数据
etf_df = etf_df.dropna(subset=['ret', 'mom12'])
etf_df = etf_df[etf_df['date'] >= '2020-01-01']
etf_df = etf_df[etf_df['date'] <= '2026-07-10']
print(f'过滤后: {etf_df["code"].nunique()}只, {len(etf_df)}行, 日期:{etf_df["date"].min()}~{etf_df["date"].max()}')

# 按日期+板块聚合（等权平均收益）
agg = etf_df.groupby(['date', 'category']).agg(
    avg_ret=('ret', 'mean'),
    avg_mom=('mom12', 'mean'),
    avg_atr=('atr_ratio', 'mean'),
    avg_vol=('vol_ratio', 'mean'),
    n_etfs=('code', 'count'),
).reset_index()
agg = agg.rename(columns={'category': 'sector'})
agg = agg.sort_values(['sector', 'date'])
print(f'板块日线: {len(agg)}行, {agg["date"].nunique()}个交易日, {agg["sector"].nunique()}个板块')

# 估值代理：用板块成交量分位（量缩=低估值信号）
agg['vol_pct'] = agg.groupby('date')['avg_vol'].rank(pct=True)
agg['val_score'] = 1 - agg['vol_pct']  # vol低=val_score高=低估

# ====================== 3. 回测 ======================
dates = sorted(agg['date'].unique())
print(f'\n回测: {dates[0]} ~ {dates[-1]}, {len(dates)}个调仓点')

results = []
for strat_name, filter_fn, note in [
    ('A_纯动量TOP1',      lambda d: d.nlargest(1,'avg_mom'),            
                          '12天动量选最强板块'),
    ('B_低估值+动量TOP1', lambda d: (d[d['val_score']>0.6].nlargest(1,'avg_mom') 
                                       if len(d[d['val_score']>0.6])>0 else d.nlargest(1,'avg_mom')), 
                          '低估板块(量缩)中选动量最强'),
    ('C_估值加权动量TOP1',lambda d: d.assign(score=d['avg_mom']*agg.loc[d.index,'val_score'] if 'val_score' in d.columns else d['avg_mom']).nlargest(1,'score'), 
                          '动量×估值加权'),
    ('D_纯低估TOP1',      lambda d: d.nsmallest(1,'val_score'),       
                          '选估值最低板块(量缩最少)'),
    ('E_动量+ATR>0.9',   lambda d: d[d['avg_atr']>0.9].nlargest(1,'avg_mom') 
                                       if len(d[d['avg_atr']>0.9])>0 else d.nlargest(1,'avg_mom'), 
                          'ATR过滤假突破'),
    ('F_三维因子',        None,  # 单独处理
                          '动量×ATR×(1-val_score)'),
]:
    if strat_name == 'F_三维因子':
        rets = []
        for d in dates:
            day = agg[agg['date'] == d].copy()
            if day.empty: continue
            day = day.dropna(subset=['avg_mom','avg_atr','val_score'])
            if day.empty: continue
            day = day[day['n_etfs'] >= 2]  # 至少2只ETF
            if day.empty: continue
            day['score'] = day['avg_mom'] * day['avg_atr'] * (1 - day['val_score'])
            sel = day.nlargest(1, 'score')
            if sel.empty: continue
            r = sel.iloc[0]['avg_mom']
            rets.append({'date': d, 'ret': r})
    else:
        rets = []
        for d in dates:
            day = agg[agg['date'] == d].copy()
            if day.empty: continue
            day = day.dropna(subset=['avg_mom'])
            day = day[day['n_etfs'] >= 2]
            if day.empty: continue
            sel = filter_fn(day)
            if sel.empty: continue
            r = sel.iloc[0]['avg_mom']
            rets.append({'date': d, 'ret': r})
    
    ret_df = pd.DataFrame(rets)
    if ret_df.empty or 'ret' not in ret_df.columns or ret_df['ret'].isna().all():
        print(f'{strat_name}: 无有效数据')
        continue
    ret_df = ret_df.dropna(subset=['ret']).set_index('date')
    if len(ret_df) == 0:
        print(f'{strat_name}: 无数据')
        continue
    
    cum = (1 + ret_df['ret']).cumprod()
    ann = cum.iloc[-1] ** (252.0 / len(cum)) - 1
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    sharpe = ret_df['ret'].mean() / ret_df['ret'].std() * np.sqrt(252) if ret_df['ret'].std() > 0 else 0
    win = (ret_df['ret'] > 0).mean()
    results.append({'strategy': strat_name, 'note': note, 'ann': ann, 'mdd': mdd, 
                    'sharpe': sharpe, 'win': win, 'n': len(ret_df)})
    print(f'{strat_name}: 年化={ann*100:.2f}% MDD={mdd*100:.2f}% Sharpe={sharpe:.2f} 胜率={win*100:.1f}% n={len(ret_df)}')

# 基准：持有所有板块等权
print('\n--- 基准: 等权持有所有板块 ---')
bench_rets = agg.groupby('date')['avg_ret'].mean()
bench_cum = (1 + bench_rets).cumprod()
bench_ann = bench_cum.iloc[-1] ** (252.0 / len(bench_cum)) - 1
bench_peak = bench_cum.cummax()
bench_mdd = ((bench_cum - bench_peak) / bench_peak).min()
bench_sharpe = bench_rets.mean() / bench_rets.std() * np.sqrt(252) if bench_rets.std() > 0 else 0
print(f'等权持有: 年化={bench_ann*100:.2f}% MDD={bench_mdd*100:.2f}% Sharpe={bench_sharpe:.2f}')

# ====================== 4. 年度明细 ======================
if results:
    print('\n=== 年度明细（最佳策略）===')
    best = max(results, key=lambda x: x['sharpe'])
    # 重建最佳策略收益
    strat_name = best['strategy']
    # 找到对应的filter
    filter_map = {
        'A_纯动量TOP1': (lambda d: d.nlargest(1,'avg_mom'), 12),
        'B_低估值+动量TOP1': (lambda d: (d[d['val_score']>0.6].nlargest(1,'avg_mom') if len(d[d['val_score']>0.6])>0 else d.nlargest(1,'avg_mom')), 12),
        'E_动量+ATR>0.9': (lambda d: d[d['avg_atr']>0.9].nlargest(1,'avg_mom') if len(d[d['avg_atr']>0.9])>0 else d.nlargest(1,'avg_mom'), 12),
    }
    if strat_name in filter_map:
        fn, _ = filter_map[strat_name]
        rets = []
        for d in dates:
            day = agg[agg['date'] == d].copy()
            if day.empty: continue
            day = day.dropna(subset=['avg_mom'])
            day = day[day['n_etfs'] >= 2]
            if day.empty: continue
            sel = fn(day)
            if sel.empty: continue
            rets.append({'date': d, 'ret': sel.iloc[0]['avg_mom'], 'year': pd.Timestamp(d).year})
        
        ret_df = pd.DataFrame(rets).dropna()
        if not ret_df.empty:
            print('\n年度收益:')
            for yr, grp in ret_df.groupby('year'):
                cum_yr = (1+grp['ret']).prod() - 1
                print(f'  {yr}: {(1+cum_yr)**(252/len(grp))-1:+.1%} 调仓{len(grp)}次')
    
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT, index=False)
    print(f'\n结果已保存: {OUT}')
    print('\n最佳策略:', best['strategy'], f"Sharpe={best['sharpe']:.2f}")
