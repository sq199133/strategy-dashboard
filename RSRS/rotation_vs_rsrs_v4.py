"""RSRS v4 vs 多资产指数轮动 — 同期对比"""
import akshare as ak
import numpy as np, pandas as pd
import json, os
import warnings; warnings.filterwarnings('ignore')

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
    extra=[c for c in df.columns if c not in ['date','wk_label']]
    ad={'date':'last'}; [ad.update({c:'last'}) for c in extra]
    ww=w.groupby('wk_label',sort=False).agg(ad).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date']); return ww

COL_K=list(INDICES.keys())
idx_wk={k:to_weekly(v) for k,v in idx_data.items()}
common=sorted(set.intersection(*[set(idx_wk[k]['date']) for k in idx_wk]))
pnl_idx=pd.DataFrame({'date':common})
for k in idx_wk:
    ww=idx_wk[k].set_index('date')
    pnl_idx[f'{k}_close']=pnl_idx['date'].map(ww['close'])
pnl_idx=pnl_idx.dropna().reset_index(drop=True)
for k in COL_K:
    pnl_idx[f'{k}_mom4']=pnl_idx[f'{k}_close'].pct_change(4).fillna(0)

def run_index_strategy(pnl_df, start, end):
    p=pnl_df.copy()
    p=p[(p['date']>=start)&(p['date']<=end)].reset_index(drop=True)
    N=len(p); p['pr']=0.0; p['weight']=0.0; p['hold']=''
    p['port_ret']=p[[f'{k}_close' for k in COL_K]].pct_change().mean(axis=1)
    p['rolling_vol']=p['port_ret'].rolling(4).std()*np.sqrt(52)
    p['scale']=p.apply(lambda r: min(1.0,0.20/max(r['rolling_vol'],0.01)) if not pd.isna(r['rolling_vol']) else 1.0, axis=1)
    for i in range(1,N):
        is_rb=(i%2)==1; sc=p['scale'].iloc[i-1]
        if is_rb:
            cands=[(k,p[f'{k}_mom4'].iloc[i-1]) for k in COL_K if p[f'{k}_mom4'].iloc[i-1]>0.05]
            if cands:
                best=max(cands,key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'hold']=best; p.loc[p.index[i],'weight']=sc
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'weight']=0
        else:
            h=p['hold'].iloc[i-1]
            if h:
                wgt=p['weight'].iloc[i-1]
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*wgt
                p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'weight']=0
    return p['pr'], (p['pr']!=0)

# ===== RSRS =====
ETFS = ['510050','510300','159915','512100','159949','512010','159928','518880']
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

etf_wk={c:to_weekly(load_etf(c)) for c in ETFS if load_etf(c) is not None}
common_etf=sorted(set.intersection(*[set(etf_wk[c]['date']) for c in etf_wk]))
pnl_etf=pd.DataFrame({'date':common_etf})
for c in etf_wk:
    ww=etf_wk[c].set_index('date')
    pnl_etf[f'{c}_close']=pnl_etf['date'].map(ww['close'])
pnl_etf=pnl_etf.dropna().reset_index(drop=True)
print(f'RSRS池 {len(etf_wk)}只, {len(pnl_etf)}行')

def calc_rsrs_weekly(df):
    df=df.copy(); N=18
    for i in range(N,len(df)):
        y=df['close'].iloc[i-N+1:i+1].values
        x=np.arange(N); A=np.vstack([x,np.ones(N)]).T
        res=np.linalg.lstsq(A,y,rcond=None)
        slope=res[0][0]; intercept=res[0][1]
        fitted=slope*x+intercept; ss_res=np.sum((y-fitted)**2); ss_tot=np.sum((y-np.mean(y))**2)
        df.loc[df.index[i],'slope']=slope
        df.loc[df.index[i],'r2']=1-ss_res/ss_tot if ss_tot>1e-10 else 0
    df['rsrs']=df['slope']*df['r2']
    df['zscore']=(df['rsrs']-df['rsrs'].rolling(180).mean())/df['rsrs'].rolling(180).std()
    return df

hs_wk=calc_rsrs_weekly(to_weekly(load_etf('510300')))

def run_rsrs_strategy(df_wk, hs_wk, start, end):
    p=df_wk.copy()
    p=p[(p['date']>=start)&(p['date']<=end)].reset_index(drop=True)
    N=len(p); p['pr']=0.0; p['hold']=''
    p['rsrs']=p['date'].map(hs_wk.set_index('date')['zscore'])
    p['sig']=p['rsrs'].apply(lambda z:1 if z>0.7 else(-1 if z<-1.0 else 0))
    p['inm']=0; pos=False
    for i in range(len(p)):
        if p['sig'].iloc[i]==1: pos=True
        elif p['sig'].iloc[i]==-1: pos=False
        p.loc[p.index[i],'inm']=1 if pos else 0
    for c in etf_wk:
        p[f'{c}_m10']=p[f'{c}_close'].pct_change(10).fillna(0)
        p[f'{c}_m12']=p[f'{c}_close'].pct_change(12).fillna(0)
        p[f'{c}_m15']=p[f'{c}_close'].pct_change(15).fillna(0)
        p[f'{c}_c63']=(p[f'{c}_m10']+p[f'{c}_m12']+p[f'{c}_m15'])/3
    p['p_ret']=p[[f'{c}_close' for c in etf_wk]].pct_change().mean(axis=1)
    p['v']=p['p_ret'].rolling(14).std()*np.sqrt(52)
    p['scl']=p.apply(lambda r:min(1.0,0.16/max(r['v'],0.01)) if not pd.isna(r['v']) else 1.0, axis=1)
    for i in range(1,N):
        if p['inm'].iloc[i]==0: p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'hold']=''; continue
        rb=(i%8)==1; sc=p['scl'].iloc[i-1]
        if rb:
            cands=[(c,p[f'{c}_c63'].iloc[i-1]) for c in etf_wk if p[f'{c}_c63'].iloc[i-1]>0]
            if cands:
                best=max(cands,key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'hold']=best
            else: p.loc[p.index[i],'pr']=0
        else:
            h=p['hold'].iloc[i-1]
            if h:
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'hold']=h
            else: p.loc[p.index[i],'pr']=0
    return p['pr'], (p['pr']!=0)

# ===== Run =====
start=pd.Timestamp('2017-01-01')
end=pd.Timestamp('2025-12-31')
pnl_idx_t=pnl_idx[(pnl_idx['date']>=start)&(pnl_idx['date']<=end)]
pnl_etf_t=pnl_etf[(pnl_etf['date']>=start)&(pnl_etf['date']<=end)]
astart=max(pnl_idx_t['date'].iloc[0], pnl_etf_t['date'].iloc[0])
aend=min(pnl_idx_t['date'].iloc[-1], pnl_etf_t['date'].iloc[-1])

print(f'回测期: {astart.date()} ~ {aend.date()}')

idx_ret,_=run_index_strategy(pnl_idx.copy(), astart, aend)
rsrs_ret,_=run_rsrs_strategy(pnl_etf.copy(), hs_wk, astart, aend)

# BH
idx_t=pnl_idx[(pnl_idx['date']>=astart)&(pnl_idx['date']<=aend)].reset_index(drop=True)
etf_t=pnl_etf[(pnl_etf['date']>=astart)&(pnl_etf['date']<=aend)].reset_index(drop=True)
bh_ret=[np.mean([idx_t[f'{k}_close'].iloc[i]/idx_t[f'{k}_close'].iloc[i-1]-1 for k in COL_K]) for i in range(1,len(idx_t))]
bh_ret=pd.Series([0.0]+bh_ret)
br_ret=[np.mean([etf_t[f'{c}_close'].iloc[i]/etf_t[f'{c}_close'].iloc[i-1]-1 for c in etf_wk]) for i in range(1,len(etf_t))]
br_ret=pd.Series([0.0]+br_ret)

def metrics(sr):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/52
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(52)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    return cagr,sh,mdd

im=metrics(idx_ret); rm=metrics(rsrs_ret); bm=metrics(bh_ret); brm=metrics(br_ret)
ip=(idx_ret!=0).mean()*100; rp=(rsrs_ret!=0).mean()*100

print(f'\n{"="*56}')
print(f'{"指标":<10}{"指数轮动":<16}{"RSRS v4":<16}{"BH指数":<16}{"BH ETF":<16}')
print('-'*74)
print(f'{"CAGR":<10}{im[0]*100:<+16.1f}%{rm[0]*100:<+16.1f}%{bm[0]*100:<+16.1f}%{brm[0]*100:<+16.1f}%')
print(f'{"Sharpe":<10}{im[1]:<16.2f}{rm[1]:<16.2f}{"-":<16}{"-":<16}')
print(f'{"MDD":<10}{-im[2]*100:<16.1f}%{-rm[2]*100:<16.1f}%{-bm[2]*100:<16.1f}%{-brm[2]*100:<16.1f}%')
print(f'{"持仓率":<10}{ip:<16.0f}%{rp:<16.0f}%{"-":<16}{"-":<16}')
print(f'{"超额BH":<10}{im[0]-bm[0]:<+16.1%}{rm[0]-brm[0]:<+16.1%}{"-":<16}{"-":<16}')
print(f'{"标的数":<10}{len(COL_K):<16}{len(etf_wk):<16}{len(COL_K):<16}{len(etf_wk):<16}')

# 分年度
print(f'\n{"年份":<8}{"指数轮动":<14}{"RSRS v4":<14}{"BH指数":<14}')
print('-'*50)
for y in sorted(pnl_idx_t['date'].dt.year.unique()):
    iy=idx_ret[(pnl_idx_t['date'].dt.year==y).values]
    ry=rsrs_ret[(pnl_etf_t['date'].dt.year==y).values]
    by=bh_ret[(idx_t['date'].dt.year==y).values]
    if len(iy)<4: continue
    ic=(1+iy).prod()**(52/len(iy))-1
    rc=(1+ry).prod()**(52/len(ry))-1 if len(ry)>0 else 0
    bc=(1+by).prod()**(52/len(by))-1
    print(f'{y:<8}{ic*100:<+14.1f}%{rc*100:<+14.1f}%{bc*100:<+14.1f}%')
