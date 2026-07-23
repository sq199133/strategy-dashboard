"""RSRS v4 vs 多资产指数轮动 — 同期对比 (修正版)"""
import akshare as ak
import numpy as np, pandas as pd
import json, os
import warnings; warnings.filterwarnings('ignore')

# ===== 策略A: 多资产指数轮动 =====
INDICES = {
    'CN50':'sh000016','CN300':'sh000300','CN500':'sh000905','CN1000':'sh000852',
    'CN2000':'sh000932','CYB':'sz399006','SP500':'.INX','NASDAQ':'.IXIC','DJI':'.DJI','COMM':'sh000066',
}
def load_index(sym):
    if sym.startswith('.'):
        df=ak.index_us_stock_sina(symbol=sym)
    else:
        df=ak.stock_zh_index_daily(symbol=sym)
    df['date']=pd.to_datetime(df['date']); return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

idx_data={k:load_index(v) for k,v in INDICES.items()}

def to_weekly(df):
    w=df.copy(); wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label',sort=False).agg({'date':'last','close':'last'}).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date']); return ww

idx_wk={k:to_weekly(v) for k,v in idx_data.items()}
common=sorted(set.intersection(*[set(idx_wk[k]['date']) for k in idx_wk]))
pnl_idx=pd.DataFrame({'date':common})
for k in idx_wk:
    ww=idx_wk[k].set_index('date')
    pnl_idx[f'{k}_close']=pnl_idx['date'].map(ww['close'])
pnl_idx=pnl_idx.dropna().reset_index(drop=True)
COL_K=list(INDICES.keys())
for k in COL_K:
    pnl_idx[f'{k}_mom4']=pnl_idx[f'{k}_close'].pct_change(4).fillna(0)

def run_index_strategy(pnl_df, start_date, end_date):
    p=pnl_df.copy()
    p=p[(p['date']>=start_date)&(p['date']<=end_date)].reset_index(drop=True)
    N=len(p); p['pr']=0.0; p['weight']=0.0; p['hold']=''
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
                p.loc[p.index[i],'pr']=ret*scaler; p.loc[p.index[i],'hold']=best; p.loc[p.index[i],'weight']=scaler
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'weight']=0
        else:
            h=p['hold'].iloc[i-1]
            if h and h!='':
                wgt=p['weight'].iloc[i-1]
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*wgt; p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'weight']=0
    return p['pr'], (p['pr']!=0)

# ===== 策略B: RSRS+C63+波动率 (短池) =====
# 排除太新的ETF: 159766(2021), 510880(2020), 515000(2019), 515900(2019)
ETFS = ['510050','510300','159915','512100','159949','512010','159928','518880']
ETFS_NAMES = {'510050':'上证50','510300':'沪深300','159915':'创业板','512100':'中证1000',
              '159949':'创业板50','512010':'医药','159928':'消费','518880':'黄金'}
DATA_DIR = r'D:\Qclaw_Trading\data\history'

def load_etf(code):
    for pre in ['sh','sz','']:
        fname = f'{pre}{code}.json' if pre else f'{code}.json'
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath,'r',encoding='utf-8') as f: data=json.load(f)
            rows=data.get('data',data.get('records',data)) if isinstance(data,dict) else data
            df=pd.DataFrame(rows)
            dc='date' if 'date' in df.columns else 'day'
            df['date']=pd.to_datetime(df[dc])
            return df[['date','close']].sort_values('date').reset_index(drop=True)
    return None

etf_data={c:load_etf(c) for c in ETFS}
etf_wk={c:to_weekly(d) for c,d in etf_data.items()}
common_etf=sorted(set.intersection(*[set(etf_wk[c]['date']) for c in etf_wk]))
pnl_etf=pd.DataFrame({'date':common_etf})
for c in etf_wk:
    ww=etf_wk[c].set_index('date')
    pnl_etf[f'{c}_close']=pnl_etf['date'].map(ww['close'])
pnl_etf=pnl_etf.dropna().reset_index(drop=True)
print(f'RSRS ETF池: {len(ETFS)}只, {len(pnl_etf)}行, {pnl_etf["date"].iloc[0].date()}~{pnl_etf["date"].iloc[-1].date()}')

# RSRS
def calc_rsrs(df, N=18, M=900):
    df=df.copy(); df['ret']=df['close'].pct_change()
    df['slope']=0.0; df['r2']=0.0
    for i in range(N,len(df)):
        y=df['close'].iloc[i-N+1:i+1].values
        x=np.arange(N); A=np.vstack([x,np.ones(N)]).T
        slope,intercept=np.linalg.lstsq(A,y,rcond=None)[0]
        residuals=y-(slope*x+intercept)
        ss_res=np.sum(residuals**2); ss_tot=np.sum((y-np.mean(y))**2)
        df.loc[df.index[i],'slope']=slope
        df.loc[df.index[i],'r2']=1-ss_res/ss_tot if ss_tot>1e-10 else 0
    df['rsrs']=df['slope']*df['r2']
    df['zscore']=(df['rsrs']-df['rsrs'].rolling(M).mean())/df['rsrs'].rolling(M).std()
    return df

HS300=load_etf('510300')
HS300=calc_rsrs(HS300)

def run_rsrs_strategy(df_wk, hs300_daily, start_date, end_date):
    p=df_wk.copy()
    p=p[(p['date']>=start_date)&(p['date']<=end_date)].reset_index(drop=True)
    N=len(p); p['pr']=0.0; p['hold']=''
    
    hs_df=hs300_daily[['date','close','zscore']].copy()
    wk=hs_df['date'].dt.isocalendar()
    hs_df['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    hs_wk=hs_df.groupby('wk_label',sort=False).agg({'date':'last','close':'last','zscore':'last'}).reset_index().sort_values('date')
    hs_wk['date']=pd.to_datetime(hs_wk['date'])
    p['rsrs']=p['date'].map(hs_wk.set_index('date')['zscore'])
    p['rsrs_signal']=p['rsrs'].apply(lambda z: 1 if z>0.7 else (-1 if z<-1.0 else 0))
    p['in_market']=0
    pos=False
    for i in range(len(p)):
        if p['rsrs_signal'].iloc[i]==1: pos=True
        elif p['rsrs_signal'].iloc[i]==-1: pos=False
        p.loc[p.index[i],'in_market']=1 if pos else 0
    
    for c in ETFS:
        p[f'{c}_mom50']=p[f'{c}_close'].pct_change(10).fillna(0)
        p[f'{c}_mom63']=p[f'{c}_close'].pct_change(12).fillna(0)
        p[f'{c}_mom75']=p[f'{c}_close'].pct_change(15).fillna(0)
        p[f'{c}_c63']=(p[f'{c}_mom50']+p[f'{c}_mom63']+p[f'{c}_mom75'])/3
    
    p['port_ret']=p[[f'{c}_close' for c in ETFS]].pct_change().mean(axis=1)
    p['roll_vol']=p['port_ret'].rolling(14).std()*np.sqrt(52)
    p['scale']=p.apply(lambda r: min(1.0,0.16/max(r['roll_vol'],0.01)) if not pd.isna(r['roll_vol']) else 1.0, axis=1)
    
    for i in range(1,N):
        if p['in_market'].iloc[i]==0:
            p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'hold']=''; continue
        rb=(i%8)==1; sc=p['scale'].iloc[i-1]
        if rb:
            cands=[(c,p[f'{c}_c63'].iloc[i-1]) for c in ETFS if p[f'{c}_c63'].iloc[i-1]>0]
            if cands:
                best=max(cands,key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'hold']=best
            else:
                p.loc[p.index[i],'pr']=0
        else:
            h=p['hold'].iloc[i-1]
            if h and h!='':
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'hold']=h
            else:
                p.loc[p.index[i],'pr']=0
    return p['pr'], (p['pr']!=0)

# ===== 同期对比 =====
start=pd.Timestamp('2017-01-01')
end=pd.Timestamp('2025-12-31')

# 找实际可用范围
pnl_idx_trim=pnl_idx[(pnl_idx['date']>=start)&(pnl_idx['date']<=end)]
pnl_etf_trim=pnl_etf[(pnl_etf['date']>=start)&(pnl_etf['date']<=end)]
actual_start=max(pnl_idx_trim['date'].iloc[0], pnl_etf_trim['date'].iloc[0])
actual_end=min(pnl_idx_trim['date'].iloc[-1], pnl_etf_trim['date'].iloc[-1])

idx_ret,_=run_index_strategy(pnl_idx.copy(), actual_start, actual_end)
rsrs_ret,_=run_rsrs_strategy(pnl_etf.copy(), HS300, actual_start, actual_end)

# BH
bh_trim=pnl_idx[(pnl_idx['date']>=actual_start)&(pnl_idx['date']<=actual_end)]
bh_v=[np.mean([bh_trim.iloc[i][k]/bh_trim.iloc[i-1][k]-1 for k in COL_K]) for i in range(1,len(bh_trim))]
bh_ret=pd.Series([0.0]+bh_v)

br_trim=pnl_etf[(pnl_etf['date']>=actual_start)&(pnl_etf['date']<=actual_end)]
br_v=[np.mean([br_trim.iloc[i][c]/br_trim.iloc[i-1][c]-1 for c in ETFS]) for i in range(1,len(br_trim))]
br_ret=pd.Series([0.0]+br_v)

def metrics(sr, wk52=52):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/wk52
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(wk52)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean()
    calmar=cagr/abs(mdd) if abs(mdd)>1e-10 else 0
    return cagr,sh,mdd,win,calmar

idx_mt=metrics(idx_ret)
rsrs_mt=metrics(rsrs_ret)
bh_mt=metrics(bh_ret)
br_mt=metrics(br_ret)

idx_pos=(idx_ret!=0).mean()*100
rsrs_pos=(rsrs_ret!=0).mean()*100

print(f'\n{"="*50}')
print(f'  同期对比: {actual_start.date()} ~ {actual_end.date()}')
print(f'{"="*50}')
print(f'{"指标":<12}{"指数轮动":<14}{"RSRS v4":<14}{"BH指数池":<14}{"BH ETF池":<14}')
print('-'*68)
for nm,val in [('CAGR',f'{idx_mt[0]*100:+.1f}%'),('Sharpe',f'{idx_mt[1]:.2f}'),('MDD',f'{-idx_mt[2]*100:.1f}%'),('Calmar',f'{idx_mt[4]:.2f}'),('持仓',f'{idx_pos:.0f}%')]:
    rv=f'{rsrs_mt[0]*100:+.1f}%' if nm=='CAGR' else (f'{rsrs_mt[1]:.2f}' if nm=='Sharpe' else(f'{-rsrs_mt[2]*100:.1f}%' if nm=='MDD' else(f'{rsrs_mt[4]:.2f}' if nm=='Calmar' else f'{rsrs_pos:.0f}%')))
    bv=f'{bh_mt[0]*100:+.1f}%' if nm=='CAGR' else(f'{-bh_mt[2]*100:.1f}%' if nm=='MDD' else'-')
    bv2=f'{br_mt[0]*100:+.1f}%' if nm=='CAGR' else(f'{-br_mt[2]*100:.1f}%' if nm=='MDD' else'-')
    print(f'{nm:<12}{val:<14}{rv:<14}{bv:<14}{bv2:<14}')

print(f'{"超额BH":<12}{idx_mt[0]-bh_mt[0]:<+14.1%}{rsrs_mt[0]-br_mt[0]:<+14.1%}')