"""
周线20周均线趋势跟踪 - 海外ETF
修正版: 修复MDD和BH年度计算
"""
import json, numpy as np, pandas as pd
warnings = __import__('warnings'); warnings.filterwarnings('ignore')

D = r'D:\QClaw_Trading\data\history'
POOL = {
    '513100':'纳指ETF','513500':'标普500','518880':'黄金','162411':'华宝油气','513050':'中概互联',
}

def load(c):
    with open(D+'/'+c+'.json','r',encoding='utf-8') as f: raw=json.load(f)
    df=pd.DataFrame(raw['records']); df['date']=pd.to_datetime(df['date'])
    return df[df['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

def to_weekly(df):
    w=df.copy(); w['wk']=w['date'].dt.isocalendar().year.astype(str)+'-W'+w['date'].dt.isocalendar().week.astype(str).str.zfill(2)
    return w.groupby('wk').agg({'date':'last','close':'last','high':'max','low':'min','open':'first'}).reset_index(drop=True).sort_values('date')

# 加载
wd={}
for c in POOL:
    wdf=to_weekly(load(c))
    if len(wdf)>=100: wd[c]=wdf

common_w=sorted(set.intersection(*[set(d['date']) for d in wd.values()]))
print(f'{len(wd)} ETFs, {len(common_w)} 周: {common_w[0].date()} ~ {common_w[-1].date()}')
panel=pd.DataFrame({'date':common_w}).set_index('date')
for c,wdf in wd.items():
    panel[c]=panel.index.map(wdf.set_index('date')['close'])
    panel[f'ma20_{c}']=panel[c].rolling(20).mean()

# 日线BH基准
daily={}
for c in POOL:
    d=load(c); d=d.set_index('date')
    daily[c]=d['close']

def get_metrics(returns):
    sr=returns.dropna(); eq=(1+sr).cumprod(); y=len(sr)/52
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(52.0)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    return cagr,sh,mdd,eq

def run_strategy(X):
    df=panel.copy()
    for c in POOL:
        above=(df[c]>df[f'ma20_{c}']).astype(int)
        above_x=above.rolling(X,min_periods=X).sum()
        below=(df[c]<=df[f'ma20_{c}']).astype(int)
        below_x=below.rolling(X,min_periods=X).sum()
        
        pos=np.zeros(len(df))
        inp=False
        for i in range(len(df)):
            if above_x.iloc[i]==X and not inp: inp=True
            if below_x.iloc[i]==X and inp: inp=False
            pos[i]=1 if inp else 0
        df[f'pos_{c}']=pos
        df[f'ret_{c}']=df[c].pct_change().fillna(0)
    
    # 等权组合
    n_pos=df[[f'pos_{c}' for c in POOL]].sum(axis=1)
    df['w']=n_pos.apply(lambda x: 1/x if x>0 else 0)
    df['pr']=sum(df[f'ret_{c}']*df[f'pos_{c}'].shift(1).fillna(0)*df['w'] for c in POOL)
    
    return df['pr'], n_pos

print(f'\n{"X":<4}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"交易次数":<10}{"持仓%":<8}')
print('-'*48)
best_x=2
for X in [1,2,3,4,5]:
    pr,pos_count=run_strategy(X)
    cagr,sh,mdd,eq=get_metrics(pr)
    # 交易次数
    tr=0
    for c in POOL:
        p=np.zeros(len(panel)); inp=False
        for i in range(1,len(panel)):
            above_x=(panel[c].iloc[i]>panel[f'ma20_{c}'].iloc[i]) if not pd.isna(panel[f'ma20_{c}'].iloc[i]) else False
            if above_x and not inp: inp=True; tr+=1
            elif not above_x and inp: inp=False
    pos_pct=(pos_count>0).sum()/len(panel)*100
    print(f'{X:<4}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{tr:<10}{pos_pct:<8.1f}')

# 单只详细
print(f'\n{"="*60}')
print(f'  X=2 单只ETF分析')
print(f'{"="*60}')
pr_all,pos_all=run_strategy(2)
for c in POOL:
    df2=panel.copy()
    above=(df2[c]>df2[f'ma20_{c}']).astype(int)
    above_x=above.rolling(2,min_periods=2).sum()
    below=(df2[c]<=df2[f'ma20_{c}']).astype(int)
    below_x=below.rolling(2,min_periods=2).sum()
    pos=np.zeros(len(df2)); inp=False
    for i in range(len(df2)):
        if above_x.iloc[i]==2 and not inp: inp=True
        if below_x.iloc[i]==2 and inp: inp=False
        pos[i]=1 if inp else 0
    pr=df2[c].pct_change().fillna(0)*pd.Series(pos).shift(1).fillna(0)
    cagr,sh,mdd,eq=get_metrics(pr)
    ret_max=eq.max(); ret_min=eq.min()
    
    # BH
    bh_s=df2[c].pct_change().fillna(0)
    _,_,_,bheq=get_metrics(bh_s)
    bh_cagr=bheq.iloc[-1]**(52/len(bh_s.dropna()))-1 if len(bh_s.dropna())>0 else 0
    pos_r=(pos.sum()/len(pos))*100
    print(f'  {POOL[c]:<10} → {cagr*100:>5.1f}% / Sh {sh:.2f} / MDD {-mdd*100:.1f}% / BH {bh_cagr*100:.1f}% / 持仓{pos_r:.0f}%')

# 组合指标
cagr,sh,mdd,eq=get_metrics(pr_all)
ret_max=eq.max(); ret_min=eq.min()
print(f'\n  {"组合总":<10} → {cagr*100:>5.1f}% / Sh {sh:.2f} / MDD {-mdd*100:.1f}%')
# BH组合(等权日线)
bh_all=pd.DataFrame(daily).dropna()
bh_ret=bh_all.pct_change().fillna(0).mean(axis=1)
bh_bh=(1+bh_ret).cumprod().dropna()
bh_y=len(bh_ret.dropna())/252
print(f'  {"BH等权":<10} → {bh_bh.iloc[-1]**(1/bh_y)-1*100:.1f}%')

# 分年度
print(f'\n  分年度 (X=2):')
print(f'  {"Year":<6}{"CAGR%":<8}{"BHday%":<8}{"XS%":<8}{"Sharpe":<8}{"MDD%":<8}')
print(f'  {"-"*46}')
for yr in range(panel.index[0].year,panel.index[-1].year+1):
    m=panel.index.year==yr
    if m.sum()<10: continue
    pr=pr_all[m]; ys=pr.dropna()
    if len(ys)<10: continue
    
    # BH日线
    bm=bh_all.loc[bh_all.index.year==yr].mean(axis=1)
    bh_yret=(1+bm).cumprod().iloc[-1]-1
    
    cagr,sh,mdd,eq=get_metrics(ys)
    print(f'  {yr:<6}{cagr*100:<8.1f}{bh_yret*100:<8.1f}{(cagr-bh_yret)*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}')
