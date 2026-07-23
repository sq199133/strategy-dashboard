"""
RSRS + C63 + 波动率 — 全球指数轮动池测试
池子: 上证50/沪深300/创业板/中证1000/纳指/标普500/黄金/原油/中概互联/创业板50
"""
import json, os, numpy as np, pandas as pd
import statsmodels.api as sm
warnings = __import__('warnings'); warnings.filterwarnings('ignore')

D = r'D:\QClaw_Trading\data\history'
POOL = {
    '510050':'SZ50','510300':'HS300','159915':'CYB','159949':'CYB50','512100':'ZZ1000',
    '513100':'NSDQ','513500':'SP500','518880':'GOLD','162411':'OIL','513050':'CNINT',
}
POOL_NAMES = ['上证50','沪深300','创业板','创业板50','中证1000','纳指ETF','标普500','黄金','华宝油气','中概互联']

def load(c):
    with open(D+'\\'+c+'.json','r',encoding='utf-8') as f: raw=json.load(f)
    df=pd.DataFrame(raw['records']); df['date']=pd.to_datetime(df['date'])
    return df[df['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

# 加载+找公共日
data={}
for c in POOL:
    df=load(c)
    if len(df)>=800: data[c]=df
    else: print(f'  SKIP {c} ({POOL[c]}): {len(df)} rows')

common=sorted(set.intersection(*[set(d['date']) for d in data.values()]))
print(f'{len(POOL)} ETFs, {len(common)} common days, {common[0].date()} ~ {common[-1].date()}')

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

def rsrs_sig(buy=0.7,sell=-1.0):
    p=0; sig=np.zeros(len(z))
    for i in range(len(z)):
        if not np.isnan(z[i]):
            if z[i]>buy: p=1
            elif z[i]<sell: p=0
        sig[i]=p
    return pd.Series([sig[i] if i<len(sig) else 0 for i in ix], index=panel.index)

# 波动率
dfi=df510.set_index('date')
av=dfi['close'].pct_change().fillna(0).rolling(70).std()*np.sqrt(252)
vol_s=(0.16/av).clip(0,1.0); vol_s[av.isna()]=1.0
vol_all=vol_s[vol_s.index.isin(set(panel.index))]

# 策略
def run(panel, sig, vol, rb=42):
    n=len(panel); pos=pd.DataFrame(0.0,index=panel.index,columns=panel.columns)
    nr=None; hold=[]
    for i,date in enumerate(panel.index):
        m=int(sig.loc[date]); sc=float(vol.loc[date]) if vol is not None else 1.0
        if not m or sc<=0:
            hold=[]; pos.loc[date]=0; nr=None
        else:
            if nr is None or date>=nr:
                cand=[]
                for c in panel.columns:
                    mom=0; wsum=0
                    for lb,w in zip([50,63,75],[1,1,1]):
                        v=panel[c].pct_change(lb).loc[date]
                        if not pd.isna(v): mom+=v*w; wsum+=w
                    mom=mom/wsum if wsum>0 else None
                    if mom is None or mom<=0: continue
                    cand.append((c,mom))
                hold=[c for c,_ in sorted(cand,key=lambda x:-x[1])[:1]] if cand else []
                nr=panel.index[min(i+rb,n-1)]
            if hold:
                w=sc/len(hold)
                for c in hold: pos.loc[date,c]=w
    return pos

# ─── 全球池（含美股+商品）───
print('\n' + '='*60)
print('  全球宏观轮动池(上证50/沪深300/创业板/创业板50/中证1000/纳指/标普500/黄金/原油/中概互联)')
print('='*60)
sig=rsrs_sig()
p1=run(panel,sig,vol_all,42)
r1=panel.pct_change().fillna(0)
sr1=(r1*p1.shift(1).fillna(0)).sum(axis=1)
eq1=(1+sr1).cumprod(); bh_r1=r1.mean(axis=1); bh_eq1=(1+bh_r1).cumprod()
y1=len(sr1)/252
tc1=eq1.iloc[-1]**(1/y1)-1
ts1=np.sqrt(252)*sr1.mean()/sr1.std() if sr1.std()>1e-10 else 0
tm1=((eq1-eq1.cummax())/eq1.cummax()).min()
tb1=bh_eq1.iloc[-1]**(1/y1)-1
print(f'  全期: {tc1*100:.1f}%  Sharpe {ts1:.2f}  MDD {-tm1*100:.1f}%  XS {(tc1-tb1)*100:.1f}%')
print(f'  BH: {tb1*100:.1f}%')
oosm1=panel.index>='2022-07-01'
y_oos1=oosm1.sum()/252
eq_oos1=(1+sr1[oosm1]).cumprod()
oc1=eq_oos1.iloc[-1]**(1/y_oos1)-1
os1=np.sqrt(252)*sr1[oosm1].mean()/sr1[oosm1].std() if sr1[oosm1].std()>1e-10 else 0
om1=((eq_oos1-eq_oos1.cummax())/eq_oos1.cummax()).min()
print(f'  OOS: {oc1*100:.1f}%  Sharpe {os1:.2f}  MDD {-om1*100:.1f}%')

# 选股统计
print('\n  选股排名:')
sel1={}
for date in p1.index:
    for c in p1.columns:
        if p1.loc[date,c]>0: sel1[c]=sel1.get(c,0)+1
for c in sorted(sel1,key=lambda x:-sel1[c]):
    print(f'    {POOL[c]:<10}: {sel1[c]:>4}d')

# 分年度
print('\n  分年度表现:')
print(f'  {"Year":<8}{"CAGR%":<8}{"BH%":<8}{"XS%":<8}{"Sharpe":<8}{"MDD%":<8}')
print(f'  {"-"*48}')
for yr in sorted(set(d.year for d in panel.index)):
    mask=panel.index.year==yr
    nd=mask.sum()
    if nd<10: continue
    ys=sr1[mask]
    yeq=(1+ys).cumprod()
    cagr=yeq.iloc[-1]**(252/nd)-1
    sh=np.sqrt(252)*ys.mean()/ys.std() if ys.std()>1e-10 else 0
    mdd=((yeq-yeq.cummax())/yeq.cummax()).min()
    bh=(1+bh_r1[mask]).cumprod().iloc[-1]**(252/nd)-1
    print(f'  {yr:<8}{cagr*100:<8.1f}{bh*100:<8.1f}{(cagr-bh)*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}')

# 持仓统计
pos_days=(p1.sum(axis=1)>0).sum()
total_days=len(p1)
print(f'\n  持仓日: {pos_days}/{total_days} ({pos_days/total_days*100:.1f}%)')
