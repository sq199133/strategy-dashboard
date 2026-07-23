"""2026年持仓明细"""
import akshare as ak
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

indices = {
    'CN50':('sh000016','上证50'),'CN300':('sh000300','沪深300'),
    'CN500':('sh000905','中证500'),'CN1000':('sh000852','中证1000'),
    'CN2000':('sh000932','中证2000'),'CYB':('sz399006','创业板指'),
    'SP500':('.INX','S&P500'),'NASDAQ':('.IXIC','纳斯达克'),
    'DJI':('.DJI','道琼斯'),'COMM':('sh000066','上证商品'),
}

def load(src,sym):
    if src=='stock_zh_index_daily':
        df=ak.stock_zh_index_daily(symbol=sym); df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym); df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(sym,name) in indices.items():
    src='stock_zh_index_daily' if k!='SP500' and k!='NASDAQ' and k!='DJI' else 'us_sina'
    d=load(src,sym)
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
NAME={k:v[1] for k,v in indices.items()}

for k in COL_K:
    pnl[f'{k}_mom4']=pnl[f'{k}_close'].pct_change(4).fillna(0)

# 运行策略
p=pnl.copy(); p['pr']=0.0; p['cat']=0; p['hold']=''; p['weight']=1.0
p['port_ret']=p[[f'{k}_close' for k in COL_K]].pct_change().mean(axis=1)
p['rolling_vol']=p['port_ret'].rolling(4).std()*np.sqrt(52)
p['scale']=p.apply(lambda r: min(1.0,0.20/max(r['rolling_vol'],0.01)) if not pd.isna(r['rolling_vol']) else 1.0, axis=1)
for i in range(1,N):
    is_rb=(i%2)==1; scaler=p['scale'].iloc[i-1]
    if is_rb:
        cands=[(k,p[f'{k}_mom4'].iloc[i-1]) for k in COL_K if p[f'{k}_mom4'].iloc[i-1]>0.05]
        if cands:
            best=max(cands,key=lambda x:x[1])[0]
            ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
            p.loc[p.index[i],'pr']=ret*scaler; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=best; p.loc[p.index[i],'weight']=scaler
        else:
            p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0
    else:
        h=p['hold'].iloc[i-1]; wgt=p['weight'].iloc[i-1]
        if h:
            ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
            p.loc[p.index[i],'pr']=ret*wgt; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
        else:
            p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0

p['date']=pnl['date']; p['year']=p['date'].dt.year
p['wk_num']=p['date'].dt.isocalendar().week

# 2026
y26=p[p['year']==2026].copy()
print(f'2026年: {len(y26)}周数据')
print(f'{"日期":<14}{"周数":<6}{"持仓":<12}{"仓位%":<8}{"周收益%":<8}{"动量%":<8}{"指数自身%":<8}{"波动率":<8}')
print('-'*75)

for idx,row in y26.iterrows():
    h=row['hold']
    wgt=row['weight']
    mom=0
    hold_self=''
    if h and h!='':
        mom = pnl.loc[idx-1,f'{h}_mom4']*100 if idx>0 else 0
        hold_self = pnl.loc[idx,f'{h}_close']/pnl.loc[idx-1,f'{h}_close']-1 if idx>0 else 0
print(f'{"日期":<14}{"周数":<6}{"持仓":<12}{"仓位%":<8}{"周收益%":<8}{"动量%":<8}{"指数自身%":<8}{"波动率%":<8}')
print('-'*75)

for idx,row in y26.iterrows():
    h=row['hold']
    wgt=row['weight']
    mom=0.0
    hold_self=0.0
    if h and h!='':
        mom = float(pnl.loc[idx-1,f'{h}_mom4'])*100 if idx>0 else 0.0
        hold_self = float(pnl.loc[idx,f'{h}_close']/pnl.loc[idx-1,f'{h}_close']-1)*100 if idx>0 else 0.0
    vol_val = float(p.loc[idx,'rolling_vol'])*100 if not pd.isna(p.loc[idx,'rolling_vol']) else 0.0
    dt=row['date'].strftime('%Y-%m-%d')
    wkn=int(row['wk_num'])
    nm=NAME.get(h,'空仓')
    rt=row['pr']*100
    print(f'{dt:<14}{wkn:<6}{nm:<12}{wgt*100:<8.0f}{rt:<+8.2f}{mom:<+8.2f}{hold_self:<+8.2f}{vol_val:<8.1f}')

# 累计
yr_ret = float((1 + y26['pr']).prod() - 1)
y26['eq'] = (1 + y26['pr']).cumprod()
print()
print(f'\n2026累计: +{yr_ret*100:.1f}%')

# 全市场各指数表现
print(f'\n2026年各指数涨幅:')
y26_idx=pnl[pnl['date'].dt.year==2026].index
for k in COL_K:
    vals=pnl.loc[y26_idx[0]:y26_idx[-1],f'{k}_close']
    ret=float(vals.iloc[-1]/vals.iloc[0]-1)
    nm=NAME[k]
    print(f'{nm:<12}{ret*100:+8.1f}%')
