"""RSRS v4 vs 多资产指数轮动 — 同期对比
回测期: 2017-01 ~ 2025-12 (对齐RSRS可用期)
"""
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

# ===== 策略A: 运行指数轮动 =====
def run_index_strategy(pnl_df, start_date, end_date):
    p=pnl_df.copy()
    p=p[(p['date']>=start_date)&(p['date']<=end_date)].reset_index(drop=True)
    N=len(p); p['pr']=0.0; p['weight']=1.0
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
            h=p['hold'].iloc[i-1]; wgt=p['weight'].iloc[i-1]
            if not h or h=='':
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'weight']=0
            else:
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*wgt; p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
    pos=(p['cat']>0).mean() if 'cat' in p.columns else 0
    return p['pr']

# ===== 策略B: RSRS+C63+波动率 (从最终策略文件读取) =====
# 直接复用 rsrs_final_strategy.py 的逻辑
ETFS = ['510050','510300','159915','512100','159949','515000','515900','512010',
        '159928','518880','159766','510880','159840']
ETF_NAMES = {'510050':'上证50','510300':'沪深300','159915':'创业板','512100':'中证1000',
             '159949':'创业板50','515000':'科技50','515900':'央企创新','512010':'医药',
             '159928':'消费','518880':'黄金','159766':'旅游','510880':'红利','159840':'锂电池'}
DATA_DIR = r'D:\Qclaw_Trading\data\history'

def load_etf_pair(code):
    """加载ETF日线，优先有前缀"""
    for pre in ['sh','sz','']:
        fname = f'{pre}{code}.json' if pre else f'{code}.json'
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath,'r',encoding='utf-8') as f:
                    data=json.load(f)
            except:
                try:
                    with open(fpath,'r',encoding='gbk') as f:
                        data=json.load(f)
                except: continue
            rows=data.get('data',data.get('records',data)) if isinstance(data,dict) else data
            df=pd.DataFrame(rows)
            date_col='date' if 'date' in df.columns else 'day'
            df['date']=pd.to_datetime(df[date_col])
            df=df.sort_values('date').reset_index(drop=True)
            return df[['date','close']]
    return None

etf_data={}
for code in ETFS:
    d=load_etf_pair(code)
    if d is not None and len(d)>800: etf_data[code]=d

# 建ETF周线面板
etf_wk={c:to_weekly(d) for c,d in etf_data.items()}
etf_common=sorted(set.intersection(*[set(etf_wk[c]['date']) for c in etf_wk]))
pnl_etf=pd.DataFrame({'date':etf_common})
for c in etf_wk:
    ww=etf_wk[c].set_index('date')
    pnl_etf[f'{c}_close']=pnl_etf['date'].map(ww['close'])
pnl_etf=pnl_etf.dropna().reset_index(drop=True)
ETFS_OK=list(etf_data.keys())
print(f'RSRS ETF池: {len(ETFS_OK)}只, 周线{len(pnl_etf)}行, {pnl_etf["date"].iloc[0].date()}~{pnl_etf["date"].iloc[-1].date()}')

# RSRS计算函数
def calc_rsrs(df, N=18, M=900):
    df=df.copy(); df['ret']=df['close'].pct_change()
    df['high_low']=df['close'].rolling(18).apply(lambda x:(x.max()-x.min())/x.min())
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

# RSRS标的
HS300=load_etf_pair('510300')
HS300_daily=calc_rsrs(HS300)

def run_rsrs_strategy(df_wk, hs300_daily, start_date, end_date):
    """RSRS周线级回测"""
    p=df_wk.copy()
    p=p[(p['date']>=start_date)&(p['date']<=end_date)].reset_index(drop=True)
    N=len(p); p['pr']=0.0; p['cat']=0; p['hold']=''
    
    # RSRS信号
    hs_wk=to_weekly(hs300_daily[['date','close','zscore']])
    p['rsrs']=p['date'].map(hs_wk.set_index('date')['zscore'])
    p['rsrs_signal']=p['rsrs'].apply(lambda z: 1 if z>0.7 else (-1 if z<-1.0 else 0))
    p['in_market']=0
    pos=False
    for i in range(len(p)):
        if p['rsrs_signal'].iloc[i]==1: pos=True
        elif p['rsrs_signal'].iloc[i]==-1: pos=False
        p.loc[p.index[i],'in_market']=1 if pos else 0
    
    # C63动量
    for c in ETFS_OK:
        p[f'{c}_mom50']=p[f'{c}_close'].pct_change(10).fillna(0)  # 10周≈50日
        p[f'{c}_mom63']=p[f'{c}_close'].pct_change(12).fillna(0)
        p[f'{c}_mom75']=p[f'{c}_close'].pct_change(15).fillna(0)
        p[f'{c}_c63']=(p[f'{c}_mom50']+p[f'{c}_mom63']+p[f'{c}_mom75'])/3
    
    # 波动率
    p['port_ret']=p[[f'{c}_close' for c in ETFS_OK]].pct_change().mean(axis=1)
    p['roll_vol']=p['port_ret'].rolling(14).std()*np.sqrt(52)  # 14周≈70日
    p['scale']=p.apply(lambda r: min(1.0,0.16/max(r['roll_vol'],0.01)) if not pd.isna(r['roll_vol']) else 1.0, axis=1)
    
    for i in range(1,N):
        if p['in_market'].iloc[i]==0:
            p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'hold']=''
            continue
        rb=(i%8)==1  # 42d≈8周
        sc=p['scale'].iloc[i-1]
        if rb:
            cands=[(c,p[f'{c}_c63'].iloc[i-1]) for c in ETFS_OK if p[f'{c}_c63'].iloc[i-1]>0]
            if cands:
                best=max(cands,key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=best
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0
        else:
            h=p['hold'].iloc[i-1]
            if h and h!='':
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret*sc; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=h
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0
    return p['pr'], p['cat']

# ===== 同期对比 =====
# 取交集时间段: 2017-01-01 ~ 2025-12-31
start=pd.Timestamp('2017-01-01')
end=pd.Timestamp('2025-12-31')

# 指数轮动
idx_ret=run_index_strategy(pnl_idx.copy(), start, end)

# RSRS策略
rsrs_ret, rsrs_cat=run_rsrs_strategy(pnl_etf.copy(), HS300_daily, start, end)

# 等权BH基准（指数轮动池）
bh_idx=pnl_idx[(pnl_idx['date']>=start)&(pnl_idx['date']<=end)][COL_K]
bh_ret=[np.mean([bh_idx.iloc[i][k]/bh_idx.iloc[i-1][k]-1 for k in COL_K]) for i in range(1,len(bh_idx))]
bh_ret=pd.Series([0.0]+bh_ret)

# BH基准（RSRS池ETF）
etf_bh=pnl_etf[(pnl_etf['date']>=start)&(pnl_etf['date']<=end)][ETFS_OK]
bh_rsrs=[np.mean([etf_bh.iloc[i][c]/etf_bh.iloc[i-1][c]-1 for c in ETFS_OK]) for i in range(1,len(etf_bh))]
bh_rsrs=pd.Series([0.0]+bh_rsrs)

def metrics(sr, wk52=52):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/wk52
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(wk52)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean()
    calmar=cagr/abs(mdd) if abs(mdd)>1e-10 else 0
    return cagr,sh,mdd,win,calmar

# 计算
idx_c,idx_s,idx_m,idx_w,idx_cm=metrics(idx_ret)
rsrs_c,rsrs_s,rsrs_m,rsrs_w,rsrs_cm=metrics(rsrs_ret)
bh_c,_,bh_m,_,_=metrics(bh_ret)
br_c,_,br_m,_,_=metrics(bh_rsrs)

idx_pos=(idx_ret!=0).mean()*100
rsrs_pos=(rsrs_cat>0).mean()*100

print(f'{"="*60}')
print(f'{"同期对比 (2017-2025, 周线)":^56}')
print(f'{"="*60}')
print(f'{"指标":<14}{"指数轮动":<16}{"RSRS v4":<16}{"BH指数池":<16}{"BH ETF池":<16}')
print('-'*60)
print(f'{"CAGR":<14}{idx_c*100:<+16.1f}{rsrs_c*100:<+16.1f}{bh_c*100:<+16.1f}{br_c*100:<+16.1f}')
print(f'{"Sharpe":<14}{idx_s:<16.2f}{rsrs_s:<16.2f}{"-":<16}{"-":<16}')
print(f'{"MDD":<14}{-idx_m*100:<16.1f}{-rsrs_m*100:<16.1f}{-bh_m*100:<16.1f}{-br_m*100:<16.1f}')
print(f'{"Calmar":<14}{idx_cm:<16.2f}{rsrs_cm:<16.2f}{"-":<16}{"-":<16}')
print(f'{"持仓率":<14}{idx_pos:<16.0f}{rsrs_pos:<16.0f}{"-":<16}{"-":<16}')
print(f'{"超额(BH)":<14}{idx_c-bh_c:<+16.1%}{rsrs_c-br_c:<+16.1%}{"-":<16}{"-":<16}')
print()

# 分年度对比
yr_idx_ret=[0.0]
for i in range(1,len(idx_ret)):
    yr_idx_ret.append(float(idx_ret.iloc[i]))
yr_idx_sr=pd.Series(yr_idx_ret)

# 直接按日期分组
idx_pd=pnl_idx[(pnl_idx['date']>=start)&(pnl_idx['date']<=end)][['date']].copy()
idx_pd['ret']=idx_ret.values
idx_pd['year']=idx_pd['date'].dt.year

rsrs_pd=pnl_etf[(pnl_etf['date']>=start)&(pnl_etf['date']<=end)][['date']].copy()
rsrs_pd['ret']=rsrs_ret.values
rsrs_pd['year']=rsrs_pd['date'].dt.year

bh_pd=pnl_idx[(pnl_idx['date']>=start)&(pnl_idx['date']<=end)][['date']].copy()
bh_pd['ret']=bh_ret.values
bh_pd['year']=bh_pd['date'].dt.year

print(f'{"年份":<8}{"指数轮动":<12}{"RSRS v4":<12}{"BH指数池":<12}{"指数超额":<12}{"RSRS超额":<12}')
print('-'*68)
years=sorted(idx_pd['year'].unique())
for y in years:
    ir=idx_pd[idx_pd['year']==y]['ret']
    rr=rsrs_pd[rsrs_pd['year']==y]['ret']
    br=bh_pd[bh_pd['year']==y]['ret']
    if len(ir)==0: continue
    ic=(1+ir).prod()**(52/len(ir))-1 if len(ir)>0 else 0
    rc=(1+rr).prod()**(52/len(rr))-1 if len(rr)>0 else 0
    bc=(1+br).prod()**(52/len(br))-1 if len(br)>0 else 0
    print(f'{y:<8}{ic*100:<+12.1f}{rc*100:<+12.1f}{bc*100:<+12.1f}{ic-bc:<+12.1%}{rc-bc:<+12.1%}')
