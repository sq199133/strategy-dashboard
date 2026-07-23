"""
周线20周均线趋势跟踪 - 海外ETF单独轮动
策略: 连续X周站上20周均线→买入, 连续X周跌破→卖出
标的: 纳指ETF/标普500/黄金/华宝油气/中概互联 (+国内参考)
"""
import json, os, numpy as np, pandas as pd
warnings = __import__('warnings'); warnings.filterwarnings('ignore')

D = r'D:\QClaw_Trading\data\history'
POOL = {
    '513100':'NSDQ','513500':'SP500','518880':'GOLD','162411':'OIL','513050':'CNINT',
}

def load(c):
    with open(D+'/'+c+'.json','r',encoding='utf-8') as f: raw=json.load(f)
    df=pd.DataFrame(raw['records']); df['date']=pd.to_datetime(df['date'])
    return df[df['close']>0].drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

def to_weekly(df):
    w=df.copy(); w['wk']=w['date'].dt.isocalendar().year.astype(str)+'-W'+w['date'].dt.isocalendar().week.astype(str).str.zfill(2)
    grp=w.groupby('wk')
    res=pd.DataFrame({
        'date':grp['date'].last(),'close':grp['close'].last(),
        'high':grp['high'].max(),'low':grp['low'].min(),'open':grp['open'].first(),
    }).reset_index(drop=True).sort_values('date')
    return res

# 加载周线数据
weekly_data={}
for c in POOL:
    wdf=to_weekly(load(c))
    if len(wdf)>=100: weekly_data[c]=wdf
    else: print(f'  SKIP {c}: {len(wdf)} weeks')

# 找公共周
common_w=sorted(set.intersection(*[set(d['date']) for d in weekly_data.values()]))
print(f'{len(weekly_data)} ETFs, {len(common_w)} common weeks: {common_w[0].date()} ~ {common_w[-1].date()}')

# 构建周线面板
w_panel=pd.DataFrame({'date':common_w}).set_index('date')
for c,wdf in weekly_data.items():
    w_panel[c]=w_panel.index.map(wdf.set_index('date')['close'])
    w_panel[f'ma20_{c}']=w_panel[c].rolling(20).mean()

# ─── 回测 ───
def backtest_weekly(panel, X, pool):
    """X=连续X周确认后入场/出场"""
    df=panel.copy()
    # 信号
    for c in pool:
        above=(df[c]>df[f'ma20_{c}']).astype(int)
        # 连续X周
        above_cons=above.rolling(X,min_periods=X).sum().fillna(0)
        df[f'sig_{c}']=((above_cons==X)).astype(int)
        # 连续X周跌破
        below=(df[c]<=df[f'ma20_{c}']).astype(int)
        below_cons=below.rolling(X,min_periods=X).sum().fillna(0)
        df[f'sell_{c}']=((below_cons==X)).astype(int)
        # 持仓状态(有记忆): 入场后持仓直到出场
        pos=np.zeros(len(df))
        inpos=False
        for i in range(len(df)):
            if df[f'sig_{c}'].iloc[i] and not inpos:
                inpos=True
            if df[f'sell_{c}'].iloc[i] and inpos:
                inpos=False
            pos[i]=1 if inpos else 0
        df[f'pos_{c}']=pos
    
    # 收益计算
    for c in pool:
        df[f'ret_{c}']=df[c].pct_change().fillna(0)
        df[f'pr_{c}']=df[f'ret_{c}']*df[f'pos_{c}'].shift(1).fillna(0)
    
    # 等权组合
    pos_cols=[f'pos_{c}' for c in pool]
    df['n_pos']=df[pos_cols].sum(axis=1)
    df['weight']=df['n_pos'].apply(lambda x: 1/x if x>0 else 0)
    df['port_ret']=0.0
    for c in pool:
        df['port_ret']+=df[f'pr_{c}']*df['weight']
    
    # BH等权
    df['bh_ret']=df[[f'ret_{c}' for c in pool]].mean(axis=1)
    
    # 指标
    sr=df['port_ret'].dropna(); bh=df['bh_ret'].dropna()
    nw=len(sr)
    eq=(1+sr).cumprod(); bh_eq=(1+bh).loc[df.index[:nw]].cumprod() if len(bh)>=nw else (1+bh).cumprod().loc[:nw]
    y=nw/52; tc=eq.iloc[-1]**(1/y)-1; tb=bh_eq.iloc[-1]**(1/y)-1
    ts=np.sqrt(52)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    tm=((eq-eq.cummax())/eq.cummax()).min()
    
    # 交易统计
    trades=0
    for c in pool:
        p=df[f'pos_{c}'].values
        trades+=sum(1 for i in range(1,len(p)) if p[i]==1 and p[i-1]==0)
    
    # 持仓日
    pos_days=(df['n_pos']>0).sum()
    
    return tc,ts,-tm,tb, trades, pos_days, len(df)

# 跑不同X值
print(f'\n{"X":<4}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Trades":<10}{"持仓周%":<10}')
print(f'{"-"*44}')
for X in [1,2,3,4,5]:
    tc,ts,md,tb,n_tr,pos_d,tot=backtest_weekly(w_panel,X,list(POOL.keys()))
    print(f'{X:<4}{tc*100:<8.1f}{ts:<8.2f}{md:<8.1f}{n_tr:<10}{pos_d/tot*100:<10.1f}')

# 详细输出最佳X
print(f'\n{"="*60}')
print(f'  X=2 详细分析')
print(f'{"="*60}')
df=w_panel.copy(); X=2
for c in POOL:
    above=(df[c]>df[f'ma20_{c}']).astype(int)
    above_cons=above.rolling(X,min_periods=X).sum().fillna(0)
    below=(df[c]<=df[f'ma20_{c}']).astype(int)
    below_cons=below.rolling(X,min_periods=X).sum().fillna(0)
    
    pos=np.zeros(len(df))
    inpos=False
    for i in range(len(df)):
        if above_cons.iloc[i]==X and not inpos: inpos=True
        if below_cons.iloc[i]==X and inpos: inpos=False
        pos[i]=1 if inpos else 0
    df[f'pos_{c}']=pos
    df[f'ret_{c}']=df[c].pct_change().fillna(0)
    df[f'pr_{c}']=df[f'ret_{c}']*df[f'pos_{c}'].shift(1).fillna(0)
    
    # 每只ETF单独指标
    sr=df[f'pr_{c}'].dropna(); eq=(1+sr).cumprod()
    y=len(sr)/52
    cagr=eq.iloc[-1]**(1/y)-1
    sh=np.sqrt(52)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    pos_r=(df[f'pos_{c}']>0).sum()/len(df)*100
    
    bh_ret=df[f'ret_{c}'].dropna()
    bh_eq=(1+bh_ret).cumprod()
    bh_cagr=bh_eq.iloc[-1]**(1/len(bh_ret)*52)-1
    
    print(f'\n  {POOL[c]:<10}: CAGR {cagr*100:>5.1f}%  Sharpe {sh:.2f}  MDD {-mdd*100:.1f}%  BH {bh_cagr*100:>5.1f}%  持仓{pos_r:.1f}%')

# 组合
pos_cols=[f'pos_{c}' for c in POOL]
df['n_pos']=df[pos_cols].sum(axis=1)
df['weight']=df['n_pos'].apply(lambda x: 1/x if x>0 else 0)
df['port_ret']=0.0
for c in POOL:
    df['port_ret']+=df[f'pr_{c}']*df['weight']
sr_p=df['port_ret'].dropna()
eq_p=(1+sr_p).cumprod()
y_p=len(sr_p)/52
cagr_p=eq_p.iloc[-1]**(1/y_p)-1
sh_p=np.sqrt(52)*sr_p.mean()/sr_p.std() if sr_p.std()>1e-10 else 0
mdd_p=((eq_p-eq_p.cummax())/eq_p.cummax()).min()
print(f'\n  {"组合":<10}: CAGR {cagr_p*100:>5.1f}%  Sharpe {sh_p:.2f}  MDD {-mdd_p*100:.1f}%')

# 分年度
print(f'\n  分年度:{df.index[0].year}-{df.index[-1].year}')
print(f'  {"Year":<6}{"CAGR%":<8}{"BH%":<8}{"XS%":<8}{"Sharpe":<8}{"MDD%":<8}')
print(f'  {"-"*46}')
# 合并日和周数据用于BH
daily_bh={}
for c in POOL:
    d=load(c); d=d.set_index('date')
    daily_bh[c]=d['close']
bh_day=pd.DataFrame(daily_bh)
bh_day=bh_day.dropna()

for yr in range(df.index[0].year,df.index[-1].year+1):
    mask=df.index.year==yr
    if mask.sum()<10: continue
    ys=df['port_ret'][mask]; yeq=(1+ys).cumprod()
    cagr=yeq.iloc[-1]**(52/len(ys))-1 if len(ys)>0 else 0
    sh=np.sqrt(52)*ys.mean()/ys.std() if ys.std()>1e-10 else 0
    mdd=((yeq-yeq.cummax())/yeq.cummax()).min()
    
    # BH等权(日线)
    bm=bh_day[bh_day.index.year==yr].mean(axis=1)
    bh_c=(1+bm).cumprod().iloc[-1]-1 if len(bm)>0 else 0
    print(f'  {yr:<6}{cagr*100:<8.1f}{bh_c*100:<8.1f}{(cagr-bh_c)*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}')
