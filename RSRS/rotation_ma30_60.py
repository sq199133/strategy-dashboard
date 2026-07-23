"""30周线/60周线 替代20周线测试
两种用法:
1. 价>MA30/MA60 作入场过滤
2. (MA5-MA30)/MA30 作均线发散指标
"""
import akshare as ak
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

indices = {
    'CN50':('stock_zh_index_daily','sh000016'), 'CN300':('stock_zh_index_daily','sh000300'),
    'CN500':('stock_zh_index_daily','sh000905'), 'CN1000':('stock_zh_index_daily','sh000852'),
    'CN2000':('stock_zh_index_daily','sh000932'), 'CYB':('stock_zh_index_daily','sz399006'),
    'SP500':('us_sina','.INX'), 'NASDAQ':('us_sina','.IXIC'),
    'DJI':('us_sina','.DJI'), 'COMM':('stock_zh_index_daily','sh000066'),
}

def load(src,sym):
    if src=='stock_zh_index_daily':
        df=ak.stock_zh_index_daily(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(s,sym) in indices.items():
    d=load(s,sym); 
    if d is not None and len(d)>500: data[k]=d

def to_weekly(df):
    w=df.copy(); wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label',sort=False).agg({'date':'last','close':'last'}).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date']); return ww

weekly={k:to_weekly(v) for k,v in data.items()}
common=sorted(set.intersection(*[set(weekly[k]['date']) for k in weekly]))
pnl=pd.DataFrame({'date':common})
for k in weekly:
    ww=weekly[k].set_index('date')
    pnl[f'{k}_close']=pnl['date'].map(ww['close'])
pnl=pnl.dropna().reset_index(drop=True); N=len(pnl)
COL_K=list(indices.keys())
print(f'面板: {N}周, {len(COL_K)}资产, {common[0].date()}~{common[-1].date()}')

# 预计算所有指标
ma_periods = [20, 30, 60]
for k in COL_K:
    c = pnl[f'{k}_close']
    for mp in ma_periods:
        pnl[f'{k}_ma{mp}'] = c.rolling(mp).mean()  # MA本线
    # 动量
    pnl[f'{k}_mom4'] = c.pct_change(4).fillna(0)   # 2月动量

def metrics(sr, weekly=52):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean(); return cagr,sh,mdd,win

def backtest(pnl, thr=0.05, rebal=2, mom='_mom4', ma_filter_col=None, ma_spread_col=None, ma_spread_thr=0.0):
    """通用回测
    ma_filter_col: 价格>MA才入场
    ma_spread_col: 均线发散列名
    ma_spread_thr: 发散阈值(如0.02=MA5比MA高2%)
    """
    p = pnl.copy()
    p['pr']=0.0; p['cat']=0; p['hold']=''
    for i in range(1,N):
        is_rebal = (i % rebal) == 1
        if is_rebal:
            cands=[]
            for k in COL_K:
                m = p[f'{k}{mom}'].iloc[i-1]
                if m <= thr: continue
                if ma_filter_col:
                    ma_val = p[f'{k}_{ma_filter_col}'].iloc[i-1]
                    close_val = p[f'{k}_close'].iloc[i-1]
                    if pd.isna(ma_val) or close_val <= ma_val: continue
                if ma_spread_col:
                    spread = p[f'{k}_{ma_spread_col}'].iloc[i-1]
                    if pd.isna(spread) or spread < ma_spread_thr: continue
                cands.append((k,m))
            if cands:
                cands.sort(key=lambda x:-x[1])
                sel=[c[0] for c in cands[:1]]
                ret=sel[0]
                w=1.0
                hold_ret=w*(p[f'{ret}_close'].iloc[i]/p[f'{ret}_close'].iloc[i-1]-1)
                p.loc[p.index[i],'pr']=hold_ret; p.loc[p.index[i],'cat']=1
                p.loc[p.index[i],'hold']=sel[0]
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'hold']=''
        else:
            hold_asset=p['hold'].iloc[i-1]
            if hold_asset:
                ret=p[f'{hold_asset}_close'].iloc[i]/p[f'{hold_asset}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'cat']=p['cat'].iloc[i-1]; p.loc[p.index[i],'hold']=hold_asset
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0
    return p

# BH基准
bhs=[np.mean([pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1 for k in COL_K]) for i in range(1,N)]
bh_c,bh_s,bh_m,bh_w=metrics(pd.Series(bhs))
print(f'BH: CAGR={bh_c*100:.1f}% Sharpe={bh_s:.2f} MDD={bh_m*100:.1f}%\n')

# ─── 测试1: 不同MA线作价格过滤 ───
print('='*72)
print('  测试1: 价>MA作入场过滤')
print('='*72)
print(f'{"Filter":<12}{"Thr":<6}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*62)

ma_results=[]
for ma_col in ['', 'ma20', 'ma30', 'ma60']:
    for thr in [0.0, 0.05]:
        for rb in [2, 4]:
            p = backtest(pnl, thr=thr, rebal=rb, mom='_mom4', 
                         ma_filter_col=ma_col if ma_col else None)
            cagr,sh,mdd,win=metrics(p['pr'])
            pos=(p['cat']>0).mean()*100
            label = ma_col if ma_col else '无MA'
            ma_results.append((label, thr, rb, cagr, sh, -mdd, win, pos))

for r in sorted(ma_results, key=lambda x:-x[4])[:12]:
    print(f'{r[0]:<12}{r[1]:<+6.2f}{r[2]*100:<8.1f}{r[3]:<8.2f}{r[4]:<8.1f}{r[5]*100:<8.0f}{r[6]:<8.0f}')

# ─── 测试2: 均线发散度作过滤 ───
print(f'\n{"="*72}')
print(f'  测试2: 均线发散度 MA5 vs MA? 作过滤')
print(f'{"="*72}')

# 先计算发散度
for k in COL_K:
    c=pnl[f'{k}_close']
    pnl[f'{k}_ma5']=c.rolling(5).mean()
    for mp in [20,30,60]:
        pnl[f'{k}_spread{mp}'] = (pnl[f'{k}_ma5'] / pnl[f'{k}_ma{mp}'] - 1).fillna(0)

# 不同发散度阈值扫描
spread_results=[]
for sp_mp in [20,30,60]:
    sp_col=f'spread{sp_mp}'
    for sp_thr in [0.0, 0.005, 0.01, 0.02, 0.03]:
        for thr_base in [0.0, 0.05]:
            p = backtest(pnl, thr=thr_base, rebal=2, mom='_mom4',
                         ma_spread_col=sp_col, ma_spread_thr=sp_thr)
            cagr,sh,mdd,win=metrics(p['pr'])
            pos=(p['cat']>0).mean()*100
            spread_results.append((sp_mp, sp_thr, thr_base, cagr, sh, -mdd, win, pos))

print(f'{"MA周期":<8}{"发散>":<8}{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*72)
for r in sorted(spread_results, key=lambda x:-x[4])[:15]:
    print(f'MA{r[0]:<4}{r[1]:<+8.2f}{r[2]:<+8.2f}{r[3]*100:<8.1f}{r[4]:<8.2f}{r[5]:<8.1f}{r[6]*100:<8.0f}{r[7]:<8.0f}')

# ─── 测试3: 30/60周线替代20周线作动量计算参考 ───
print(f'\n{"="*72}')
print(f'  测试3: 相对MA的动量 (Close/MA 替代 纯Close动量)')
print(f'{"="*72}')

for k in COL_K:
    c=pnl[f'{k}_close']
    for mp in [20,30,60]:
        # 价格相对MA的比率 (涨跌幅修正)
        pnl[f'{k}_rel_ma{mp}'] = (c / pnl[f'{k}_ma{mp}']).fillna(1.0)
    # 4周相对MA动量
    for mp in [20,30,60]:
        rel = pnl[f'{k}_rel_ma{mp}']
        pnl[f'{k}_relmom{mp}'] = (rel / rel.shift(4) - 1).fillna(0)

print(f'{"动量源":<12}{"Thr":<6}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*62)

rel_results=[]
# 基准: 纯close动量
p=backtest(pnl, thr=0.05, rebal=2, mom='_mom4')
cagr,sh,mdd,win=metrics(p['pr'])
pos=(p['cat']>0).mean()*100
rel_results.append(('纯Close', 0.05, cagr, sh, -mdd, win, pos))
print(f'{"纯Close":<12}{0.05:<+6.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd:<8.1f}{win*100:<8.0f}{pos:<8.0f}')

for mp in [20,30,60]:
    momc=f'_relmom{mp}'
    for thr_b in [0.0, 0.05]:
        p=backtest(pnl, thr=thr_b, rebal=2, mom=momc)
        cagr,sh,mdd,win=metrics(p['pr'])
        pos=(p['cat']>0).mean()*100
        label=f'relMA{mp}'
        rel_results.append((label, thr_b, cagr, sh, -mdd, win, pos))
        print(f'{label:<12}{thr_b:<+6.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd:<8.1f}{win*100:<8.0f}{pos:<8.0f}')

print(f'\nBH: CAGR={bh_c*100:.1f}% Sharpe={bh_s:.2f} MDD={-bh_m*100:.1f}%')
