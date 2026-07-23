"""波动率目标提升测试: 20%→40%
固定 VW=4w, 扫描更高 TVol
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
        df=ak.stock_zh_index_daily(symbol=sym); df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym); df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(s,sym) in indices.items():
    d=load(s,sym)
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

for k in COL_K:
    pnl[f'{k}_mom4'] = pnl[f'{k}_close'].pct_change(4).fillna(0)

def metrics(sr, weekly=52):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean(); return cagr,sh,mdd,win

# 扫描: 固定VW=4w, TVol从20%到40%
print(f'{"TVol":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"AvgWgt":<8}{"Scale<0.5":<8}')
print('-'*48)

for tv in [0.20, 0.22, 0.25, 0.28, 0.30, 0.35, 0.40, 0.50, 0.60, 1.0]:
    p=pnl.copy(); p['pr']=0.0; p['cat']=0; p['hold']=''; p['weight']=1.0
    p['port_ret']=p[[f'{k}_close' for k in COL_K]].pct_change().mean(axis=1)
    p['rolling_vol']=p['port_ret'].rolling(4).std()*np.sqrt(52)
    p['scale']=p.apply(lambda r: min(1.0, tv/max(r['rolling_vol'], 0.01)) if not pd.isna(r['rolling_vol']) else 1.0, axis=1)
    
    for i in range(1,N):
        is_rb=(i%2)==1; scaler=p['scale'].iloc[i-1]
        if is_rb:
            cands=[(k,p[f'{k}_mom4'].iloc[i-1]) for k in COL_K if p[f'{k}_mom4'].iloc[i-1] > 0.05]
            if cands:
                best=max(cands,key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*scaler; p.loc[p.index[i],'cat']=1
                p.loc[p.index[i],'hold']=best; p.loc[p.index[i],'weight']=scaler
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'weight']=0
        else:
            h=p['hold'].iloc[i-1]; wgt=p['weight'].iloc[i-1]
            if h:
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*wgt; p.loc[p.index[i],'cat']=1
                p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'weight']=0
    
    cagr,sh,mdd,win=metrics(p['pr'])
    avg_wgt=p['weight'].mean()*100
    low=(p['scale']<0.5).mean()*100
    print(f'{tv:<8.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{avg_wgt:<8.0f}{low:<8.0f}')
