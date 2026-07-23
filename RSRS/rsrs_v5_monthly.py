"""
RSRS v5 — 加入月线MA12(日线MA252)长期趋势过滤
================================================
三种变体对比：
  V0: 现有C63 Top1 rb=42 (baseline)
  V1: HS300月线MA252动态调整RSRS买入阈值
  V2: ETF自身月线MA252给C63动量加分
  V3: V1+V2叠加
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

# 加载
data={}
for c in POOL:
    df=load(c)
    if len(df)>=800: data[c]=df
    else: print(f'  SKIP {c}: {len(df)} rows')

common=sorted(set.intersection(*[set(d['date']) for d in data.values()]))
print(f'13 ETFs, {len(common)} days, {common[0].date()} ~ {common[-1].date()}')

panel=pd.DataFrame({'date':common}).set_index('date')
for c,df in data.items():
    panel[c]=panel.index.map(df.set_index('date')['close'])

# RSRS
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

def rsrs_signal(buy_thr, sell_thr):
    p=0; sig=np.zeros(len(z))
    for i in range(len(z)):
        if not np.isnan(z[i]):
            if z[i]>buy_thr: p=1
            elif z[i]<sell_thr: p=0
        sig[i]=p
    return pd.Series([sig[i] if i<len(sig) else 0 for i in ix], index=panel.index)

# MA252 (≈月线MA12)
hs300_close=df510.set_index('date')['close']
hs300_ma252=hs300_close.rolling(252).mean()
close_all=panel.copy()
for c in panel.columns:
    close_all[f'ma_{c}']=panel[c].rolling(252).mean()

def run_strategy(panel, sig_series, vol_scaling, rebalance=42, etf_boost=False, hs300_adapt=False):
    """运行策略，支持MA252动态调整"""
    n=len(panel); pos=pd.DataFrame(0.0,index=panel.index,columns=panel.columns)
    nr=None; hold=[]
    for i,date in enumerate(panel.index):
        m=int(sig_series.loc[date]) if date in sig_series.index else 0
        sc=float(vol_scaling.loc[date]) if vol_scaling is not None else 1.0
        if not m or sc<=0:
            hold=[]; pos.loc[date]=0; nr=None
        else:
            if nr is None or date>=nr:
                cand=[]
                for c in panel.columns:
                    # 基准C63
                    mom=0; wsum=0
                    for lb,w in zip([50,63,75],[1,1,1]):
                        r=panel[c].pct_change(lb)
                        v=r.loc[date] if date in r.index and not pd.isna(r.loc[date]) else np.nan
                        if not pd.isna(v): mom+=v*w; wsum+=w
                    mom=mom/wsum if wsum>0 else None
                    if mom is None or mom<=0: continue
                    # V2: ETF本身在MA252之上→加分
                    if etf_boost and date in close_all.index:
                        ma=close_all.loc[date,f'ma_{c}'] if f'ma_{c}' in close_all.columns else np.nan
                        if not pd.isna(ma) and panel.loc[date,c]>ma:
                            mom*=(1+0.1)  # 在趋势上+10%动量分
                    cand.append((c,mom))
                hold=[c for c,_ in sorted(cand,key=lambda x:-x[1])[:1]] if cand else []
                nr=panel.index[min(i+rebalance,n-1)]
            if hold:
                w=sc/len(hold)
                for c in hold: pos.loc[date,c]=w
    return pos

# 波动率
dfi=df510.set_index('date')
av=dfi['close'].pct_change().fillna(0).rolling(70).std()*np.sqrt(252)
vol_s=(0.16/av).clip(0,1.0); vol_s[av.isna()]=1.0
vol_all=vol_s[vol_s.index.isin(set(panel.index))]

# ─── 测试4种变体 ───
variants={
    'V0 Baseline':       {'buy':0.7,'sell':-1.0,'etf_boost':False,'hs300_adapt':False},
    'V1 HS300_MA252':    {'buy':0.7,'sell':-1.0,'etf_boost':False,'hs300_adapt':True},
    'V2 ETF_MA252':      {'buy':0.7,'sell':-1.0,'etf_boost':True,'hs300_adapt':False},
    'V3 Combined':       {'buy':0.7,'sell':-1.0,'etf_boost':True,'hs300_adapt':True},
}
# 再加一组调参
for hsig in [0.5, 0.4]:
    for esig in [1.2, 0.9]:
        variants[f'V3_b{hsig}_sell{esig}']={'buy':0.7,'sell':-1.0,'etf_boost':True,'hs300_adapt':True,'hsig':hsig,'esig':esig}

for name,v in variants.items():
    buy_thr,sell_thr=v['buy'],v['sell']
    
    if v.get('hs300_adapt',False):
        # 动态RSRS阈值：HS300在MA252之上→放宽买入，之下→收紧
        dyn_bt=np.full(len(panel), 0.7)
        dyn_st=np.full(len(panel), -1.0)
        for i,date in enumerate(panel.index):
            ma=hs300_ma252.loc[date] if date in hs300_ma252.index else np.nan
            if not pd.isna(ma) and dfi.loc[date,'close']>ma:
                dyn_bt[i]=v.get('hsig',0.5)  # 多头市放宽
            else:
                dyn_bt[i]=v.get('esig',1.2)  # 空头市收紧
        sig=pd.Series(0,index=panel.index)
        p=0
        for i,date in enumerate(panel.index):
            zi=z[ix[i]] if ix[i]<len(z) else np.nan
            if not np.isnan(zi):
                if zi>dyn_bt[i]: p=1
                elif zi<dyn_st[i]: p=0
            sig.iloc[i]=p
    else:
        sig=rsrs_signal(buy_thr,sell_thr)
    
    boost=v.get('etf_boost',False)
    pos=run_strategy(panel,sig,vol_all,42,boost,v.get('hs300_adapt',False))
    
    r=panel.pct_change().fillna(0)
    sr=(r*pos.shift(1).fillna(0)).sum(axis=1)
    eq=(1+sr).cumprod()
    bh_r=r.mean(axis=1); bh_eq=(1+bh_r).cumprod()
    
    y=len(sr)/252; tc=eq.iloc[-1]**(1/y)-1
    ts=np.sqrt(252)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    tm=((eq-eq.cummax())/eq.cummax()).min()
    tb=bh_eq.iloc[-1]**(1/y)-1
    
    # OOS (2022.07~)
    oosm=panel.index>='2022-06-30'
    y_oos=oosm.sum()/252
    eq_oos=(1+sr[oosm]).cumprod()
    oc=eq_oos.iloc[-1]**(1/y_oos)-1
    os=np.sqrt(252)*sr[oosm].mean()/sr[oosm].std() if sr[oosm].std()>1e-10 else 0
    om=((eq_oos-eq_oos.cummax())/eq_oos.cummax()).min()
    
    print(f'\n{'='*60}')
    print(f'  {name}')
    print(f'{"="*60}')
    print(f'    ALL: {tc*100:.1f}% / Sh {ts:.2f} / MDD {tm*100:.1f}% / XS {(tc-tb)*100:.1f}%')
    print(f'    OOS: {oc*100:.1f}% / Sh {os:.2f} / MDD {om*100:.1f}%')
    print(f'    B&H ALL: {tb*100:.1f}%')
