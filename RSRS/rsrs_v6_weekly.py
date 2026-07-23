"""
RSRS v6 — 加入周线级别趋势信号
================================
日线→周线聚合，测试周线MACD和20周均线作为中周期趋势过滤

变体：
  V0: Baseline (当前RSRS+C63+波动率)
  V1: HS300周线MACD>0作为大环境过滤
  V2: ETF周线>20周均线作为持仓过滤  
  V3: ETF周线MACD偏离度作为动量加分
"""
import json, os, numpy as np, pandas as pd
import statsmodels.api as sm
warnings = __import__('warnings'); warnings.filterwarnings('ignore')

D = r'D:\QClaw_Trading\data\history'
POOL = {
    '510300':'HS300','510050':'SH50','159902':'ZZSM100','159949':'CYB50','512100':'ZZ1000',
    '159928':'CONSUM','512800':'BANK','512400':'METAL','512200':'REALEST','510160':'INDUP',
    '518880':'GOLD','159905':'DIV','510810':'SHGQ',
}

def load(c):
    with open(D+'\\'+c+'.json','r',encoding='utf-8') as f: raw=json.load(f)
    df=pd.DataFrame(raw['records']); df['date']=pd.to_datetime(df['date'])
    return df[df['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

# 加载 + 日线→周线聚合
def to_weekly(df):
    """日线→周线: 取周五(或当周最后交易日)的OHLC, 成交量求和"""
    w=df.copy(); w['week']=w['date'].dt.isocalendar().year.astype(str)+'-W'+w['date'].dt.isocalendar().week.astype(str).str.zfill(2)
    grp=w.groupby('week')
    res=pd.DataFrame({
        'date':grp['date'].last(),'close':grp['close'].last(),
        'high':grp['high'].max(),'low':grp['low'].min(),'open':grp['open'].first(),
    }).reset_index(drop=True).sort_values('date')
    return res

data={}
for c in POOL:
    df=load(c); wdf=to_weekly(df)
    if len(wdf)>=160: data[c]=wdf  # ≈3年周线
    else: print(f'  SKIP {c}: {len(wdf)} weekly rows')

# 日线面板(用于RSRS和日频调仓)
day_data={}
for c in POOL:
    df=load(c)
    if len(df)>=800: day_data[c]=df

common_day=sorted(set.intersection(*[set(d['date']) for d in day_data.values()]))
panel=pd.DataFrame({'date':common_day}).set_index('date')
for c,df in day_data.items():
    panel[c]=panel.index.map(df.set_index('date')['close'])
print(f'13 ETFs, {len(panel)} daily rows, {panel.index[0].date()} ~ {panel.index[-1].date()}')

# RSRS (from daily)
df510=load('510300')
h,l=df510['high'].values,df510['low'].values
b=np.full(len(df510),np.nan)
for i in range(17,len(df510)):
    y,x=h[i-17:i+1],l[i-17:i+1]
    if not np.isnan(x).any() and not np.isnan(y).any():
        try: b[i]=sm.OLS(y,sm.add_constant(x)).fit().params[1]
        except: pass
z=np.full(len(b),np.nan)
for i in range(899,len(b)):
    v=b[i-899:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: z[i]=(b[i]-mu)/sg

rd=df510['date'].values.astype('datetime64[ns]')
pd_ns=panel.index.values.astype('datetime64[ns]')
ix=np.searchsorted(rd,pd_ns)

def rsrs_sig(buy=0.7,sell=-1.0):
    p=0; sig=np.zeros(len(z))
    for i in range(len(z)):
        if not np.isnan(z[i]):
            if z[i]>buy: p=1
            elif z[i]<sell: p=0
        sig[i]=p
    return pd.Series([sig[i] if i<len(sig) else 0 for i in ix], index=panel.index)

# 波动率(日级别)
dfi=df510.set_index('date')
av=dfi['close'].pct_change().fillna(0).rolling(70).std()*np.sqrt(252)
vol_s=(0.16/av).clip(0,1.0); vol_s[av.isna()]=1.0
vol_all=vol_s[vol_s.index.isin(set(panel.index))]

# ─── 周线信号计算 ───
weekly_hs=to_weekly(df510).set_index('date')
weekly_hs['ma20']=weekly_hs['close'].rolling(20).mean()
weekly_hs['ema12']=weekly_hs['close'].ewm(span=12).mean()
weekly_hs['ema26']=weekly_hs['close'].ewm(span=26).mean()
weekly_hs['macd']=weekly_hs['ema12']-weekly_hs['ema26']
weekly_hs['macd_sig']=weekly_hs['macd'].ewm(span=9).mean()
weekly_hs['macd_hist']=weekly_hs['macd']-weekly_hs['macd_sig']
weekly_hs['rsi14']=weekly_hs['close'].pct_change().rolling(14).apply(lambda x: 100-100/(1+(x[x>0].sum()/abs(x[x<0].sum())) if abs(x[x<0].sum())>0 else 100)).fillna(50)

# 周线数据对齐到日线: 每周五的信号持有到下周
def weekly_to_daily(wsignal, daily_index):
    """周信号→日信号: 每周五的信号应用到下周一到下周五"""
    w_dates=wsignal.index
    daily_sig=pd.Series(0.0,index=daily_index)
    for i,wdate in enumerate(w_dates):
        if i<len(w_dates)-1:
            mask=(daily_index>=wdate)&(daily_index<w_dates[i+1])
        else:
            mask=daily_index>=wdate
        daily_sig[mask]=wsignal.loc[wdate]
    return daily_sig

# 每个ETF的周线数据
etf_weekly={}
for c in POOL:
    if c=='510300': continue
    wdf=to_weekly(load(c)).set_index('date')
    wdf['ma20']=wdf['close'].rolling(20).mean()
    wdf['ema12']=wdf['close'].ewm(span=12).mean()
    wdf['ema26']=wdf['close'].ewm(span=26).mean()
    wdf['macd']=wdf['ema12']-wdf['ema26']
    etf_weekly[c]=wdf

# ─── 策略运行 ───
def run(panel, sig_series, vol, rebalance=42, filter=None):
    """filter: 'macd'|'ma20'|'etf_macd'|None"""
    n=len(panel); pos=pd.DataFrame(0.0,index=panel.index,columns=panel.columns)
    nr=None; hold=[]
    for i,date in enumerate(panel.index):
        m=int(sig_series.loc[date]) if date in sig_series.index else 0
        sc=float(vol.loc[date]) if vol is not None else 1.0
        if not m or sc<=0:
            hold=[]; pos.loc[date]=0; nr=None
        else:
            if nr is None or date>=nr:
                # 周线过滤条件
                wfilter_ok=True
                if filter=='macd':
                    wds=weekly_hs.index.searchsorted(date)
                    if wds>0:
                        last_macd=weekly_hs['macd'].iloc[wds-1]
                        if last_macd<=0: wfilter_ok=False
                elif filter=='ma20':
                    wds=weekly_hs.index.searchsorted(date)
                    if wds>0:
                        last_close=weekly_hs['close'].iloc[wds-1]
                        last_ma20=weekly_hs['ma20'].iloc[wds-1]
                        if last_close<=last_ma20: wfilter_ok=False
                
                if not wfilter_ok:
                    hold=[]; nr=panel.index[min(i+rebalance,n-1)]
                    continue
                
                cand=[]
                for c in panel.columns:
                    mom=0; wsum=0
                    for lb,w in zip([50,63,75],[1,1,1]):
                        r=panel[c].pct_change(lb)
                        v=r.loc[date] if date in r.index and not pd.isna(r.loc[date]) else np.nan
                        if not pd.isna(v): mom+=v*w; wsum+=w
                    mom=mom/wsum if wsum>0 else None
                    if mom is None or mom<=0: continue
                    
                    # ETF周线MACD加分
                    if filter=='etf_macd' and c in etf_weekly:
                        we=etf_weekly[c]
                        wds=we.index.searchsorted(date)
                        if wds>0:
                            last_macd=we['macd'].iloc[wds-1]
                            if last_macd>0:
                                mom*=1.15  # MACD>0加分15%
                    
                    cand.append((c,mom))
                hold=[c for c,_ in sorted(cand,key=lambda x:-x[1])[:1]] if cand else []
                nr=panel.index[min(i+rebalance,n-1)]
            if hold:
                w=sc/len(hold)
                for c in hold: pos.loc[date,c]=w
    return pos

def eval_strat(pos, panel, label):
    r=panel.pct_change().fillna(0)
    sr=(r*pos.shift(1).fillna(0)).sum(axis=1)
    eq=(1+sr).cumprod(); bh_r=r.mean(axis=1); bh_eq=(1+bh_r).cumprod()
    y=len(sr)/252; tc=eq.iloc[-1]**(1/y)-1
    ts=np.sqrt(252)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    tm=((eq-eq.cummax())/eq.cummax()).min(); tb=bh_eq.iloc[-1]**(1/y)-1
    
    oosm=panel.index>='2022-06-30'
    y_oos=oosm.sum()/252; eq_oos=(1+sr[oosm]).cumprod()
    oc=eq_oos.iloc[-1]**(1/y_oos)-1
    os=np.sqrt(252)*sr[oosm].mean()/sr[oosm].std() if sr[oosm].std()>1e-10 else 0
    om=((eq_oos-eq_oos.cummax())/eq_oos.cummax()).min()
    
    print(f'  {label:<30} ALL: {tc*100:>5.1f}%/{ts:.2f}/{-tm*100:.1f}%  OOS: {oc*100:>5.1f}%/{os:.2f}/{-om*100:.1f}%  XS: {(tc-tb)*100:>4.1f}%')
    return tc,ts,tm,oc,os,om

sig_baseline=rsrs_sig()
print('\n  V0: Baseline (RSRS+Volume+波动率)')
eval_strat(run(panel,sig_baseline,vol_all,42,None),panel,'')

# V1: HS300周线MACD>0过滤
print('\n  V1: HS300周线MACD>0 大盘中周期过滤')
eval_strat(run(panel,sig_baseline,vol_all,42,'macd'),panel,'')

# V1a: HS300周线>20周均线
print('\n  V1a: HS300周线>20周均线 过滤')
eval_strat(run(panel,sig_baseline,vol_all,42,'ma20'),panel,'')

# V2: ETF周线MACD加分
print('\n  V2: ETF周线MACD>0 动量+15%')
eval_strat(run(panel,sig_baseline,vol_all,42,'etf_macd'),panel,'')
