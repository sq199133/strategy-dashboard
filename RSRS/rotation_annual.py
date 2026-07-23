"""分年度回测: 最优策略 Mom=4w Rebal=2w Thr=5% Top1 VW=4w TVol=20%
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
    pnl[f'{k}_mom4']=pnl[f'{k}_close'].pct_change(4).fillna(0)

def run_strategy(pnl, tv=0.20):
    p=pnl.copy(); p['pr']=0.0; p['cat']=0; p['hold']=''; p['weight']=1.0
    p['port_ret']=p[[f'{k}_close' for k in COL_K]].pct_change().mean(axis=1)
    p['rolling_vol']=p['port_ret'].rolling(4).std()*np.sqrt(52)
    p['scale']=p.apply(lambda r: min(1.0,tv/max(r['rolling_vol'],0.01)) if not pd.isna(r['rolling_vol']) else 1.0, axis=1)
    for i in range(1,N):
        is_rb=(i%2)==1; scaler=p['scale'].iloc[i-1]
        if is_rb:
            cands=[(k,p[f'{k}_mom4'].iloc[i-1]) for k in COL_K if p[f'{k}_mom4'].iloc[i-1]>0.05]
            if cands:
                best=max(cands,key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*scaler; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=best; p.loc[p.index[i],'weight']=scaler
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'weight']=0
        else:
            h=p['hold'].iloc[i-1]; wgt=p['weight'].iloc[i-1]
            if h:
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*wgt; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'weight']=0
    return p

# 运行策略 - 第0周无收益
res=run_strategy(pnl)
res['date']=pnl['date']
res['year']=res['date'].dt.year

# BH基准
bhs=[np.mean([pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1 for k in COL_K]) for i in range(1,N)]
pnl['bh_ret']=[0.0]+bhs
pnl['year']=pnl['date'].dt.year

# 分年度
years=sorted(res['year'].unique())
print(f'{"年份":<8}{"策略":<10}{"BH":<10}{"超额":<10}{"持仓":<8}{"AvgWgt":<8}{"MDD":<10}{"选标频":<8}')
print('-'*72)

total_sr=pd.Series(dtype=float); total_bh=pd.Series(dtype=float)
cum_sr=[]; cum_bh=[]

for y in years:
    ym=res[res['year']==y]
    if len(ym)<5: continue
    yr=ym['pr'].dropna()
    bhr=pd.Series(pnl[pnl['year']==y]['bh_ret'].dropna())
    if len(yr)==0: continue
    
    sr_cagr=(1+yr).prod()**(52/len(yr))-1 if len(yr)>0 else 0
    bh_cagr=(1+bhr).prod()**(52/len(bhr))-1 if len(bhr)>0 else 0
    excess=sr_cagr-bh_cagr
    pos=(ym['cat']>0).mean()*100
    avg_w=ym['weight'].mean()*100
    eq=(1+yr).cumprod()
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    
    # 选出前3的标的
    top3=ym[ym['hold']!='']['hold'].value_counts().head(3)
    top3_str='/'.join([f'{k}({v})' for k,v in top3.items()]) if len(top3)>0 else '-'
    
    print(f'{y:<8}{sr_cagr*100:<+10.1f}{bh_cagr*100:<+10.1f}{excess*100:<+10.1f}{pos:<8.0f}{avg_w:<8.0f}{mdd*100:<+10.1f}{top3_str:<20}')
    
    cum_sr.extend([(1+yr).prod()**(52/len(yr))-1])
    cum_bh.extend([(1+bhr).prod()**(52/len(bhr))-1])
    # 汇总用
    total_sr=pd.concat([total_sr,yr])
    total_bh=pd.concat([total_bh,bhr])

# 全期
all_cagr=(1+total_sr).prod()**(52/len(total_sr))-1
all_bh=(1+total_bh).prod()**(52/len(total_bh))-1
all_excess=all_cagr-all_bh
all_pos=(res['cat']>0).mean()*100
all_wgt=res['weight'].mean()*100
eq_all=(1+total_sr).cumprod()
all_mdd=((eq_all-eq_all.cummax())/eq_all.cummax()).min()
sh=np.sqrt(52)*total_sr.mean()/total_sr.std()

print('-'*72)
print(f'{"全期":<8}{all_cagr*100:<+10.1f}{all_bh*100:<+10.1f}{all_excess*100:<+10.1f}{all_pos:<8.0f}{all_wgt:<8.0f}{all_mdd*100:<+10.1f}Sharpe={sh:.2f}')

# 连续复利曲线
eq_st=(1+res['pr'].fillna(0)).cumprod()
pnl['eq_strat']=eq_st.values
eq_bh=(1+pnl['bh_ret']).cumprod()
pnl['eq_bh']=eq_bh.values

print('\n--- 年度表现总结 ---')
strong=[y for y in years if len(res[res['year']==y])>=5]
for y in strong:
    ym=res[res['year']==y]
    yr=ym['pr'].dropna()
    if len(yr)>0:
        c=(1+yr).prod()**(52/len(yr))-1
        n=(ym['hold']!='').sum()
        t=f"{y}: {c*100:+.1f}% (持仓{n}/{len(ym)}周)"
        print(t)
