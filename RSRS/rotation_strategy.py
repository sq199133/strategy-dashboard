"""多资产池：周线趋势过滤+相对动量轮动
策略架构：
1. 绝对趋势过滤：仅当资产价格>周线MA20时允许持仓
2. 相对动量轮动：在可持仓的资产中，选过去N周动量最强的Top-K
3. 对比基准：等权BH、50/50等"""
import akshare as ak
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

indices = {
    'CN50':('stock_zh_index_daily','sh000016'),
    'CN300':('stock_zh_index_daily','sh000300'),
    'CN500':('stock_zh_index_daily','sh000905'),
    'CN1000':('stock_zh_index_daily','sh000852'),
    'CN2000':('stock_zh_index_daily','sh000932'),
    'CYB':('stock_zh_index_daily','sz399006'),
    'SP500':('us_sina','.INX'),
    'NASDAQ':('us_sina','.IXIC'),
    'DJI':('us_sina','.DJI'),
    'COMM':('stock_zh_index_daily','sh000066'),
}

def load(src,sym):
    if src=='stock_zh_index_daily':
        df=ak.stock_zh_index_daily(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

# 加载
data={}
for k,(s,sym) in indices.items():
    d=load(s,sym)
    if d is not None and len(d)>500:
        data[k]=d
        print(f'{k:<8}{s:<25}{len(d):>5}行 {d.iloc[0]["date"].date()}')

# 转周线
weekly={}
for k,d in data.items():
    w=d.copy()
    wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label').agg({'date':'last','close':'last'}).reset_index().sort_values('date')
    ww['ma20']=ww['close'].rolling(20).mean()
    ww['mom12']=ww['close'].pct_change(12).fillna(0)
    ww['mom6']=ww['close'].pct_change(6).fillna(0)
    weekly[k]=ww

# 找公用周
common=sorted(set.intersection(*[set(weekly[k]['date']) for k in weekly]))
print(f'\n公用日期: {len(common)}周  {common[0].date()} ~ {common[-1].date()}')

# 建面板
pnl=pd.DataFrame({'date':common})
for k in weekly:
    ww=weekly[k].set_index('date')
    pnl[f'{k}_close']=pnl['date'].map(ww['close'])
    pnl[f'{k}_ma20']=pnl['date'].map(ww['ma20'])
    pnl[f'{k}_mom12']=pnl['date'].map(ww['mom12'])
    pnl[f'{k}_mom6']=pnl['date'].map(ww['mom6'])
pnl=pnl.dropna().reset_index(drop=True)

N=len(pnl); K=len(indices)-1  # 去掉KCB
print(f'面板: {N}周 x {K}资产')

# ── 回测函数 ──
def backtest(pnl, top_k=2, mom='mom12', ma_filter=True, ma_period=20, thr=0.0):
    """回测动量轮动+MA过滤+阈值触发
    thr: 动量绝对值阈值, Top-K只有动量>thr才入场, 否则空仓
    """
    pnl['pr']=0.0; pnl['bh']=0.0
    pnl['n_active']=0
    
    for i in range(1, N):
        # BH收益 (平均)
        bh_rets=[]
        for k in indices:
            ret=(pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1)
            bh_rets.append(ret)
        pnl.loc[pnl.index[i],'bh']=np.mean(bh_rets)
        
        # 筛选可持仓资产
        candidates=[]
        for k in indices:
            if ma_filter:
                close_prev=pnl[f'{k}_close'].iloc[i-1]
                ma_prev=pnl[f'{k}_ma20'].iloc[i-1]
                if close_prev<=ma_prev:
                    continue
            candidates.append(k)
        
        if not candidates:
            pnl.loc[pnl.index[i],'pr']=0
            pnl.loc[pnl.index[i],'n_active']=0
            continue
        
        # 动量排序 (动量=过去N周涨跌幅, 归一化到0-1之间的值)
        moms=[(k,pnl[f'{k}_{mom}'].iloc[i-1]) for k in candidates]
        moms.sort(key=lambda x:-x[1])
        
        # 阈值过滤: 最强动量的资产必须超过阈值才入场
        if moms[0][1] <= thr:
            pnl.loc[pnl.index[i],'pr']=0
            pnl.loc[pnl.index[i],'n_active']=0
            continue
        
        selected=[m[0] for m in moms[:top_k]]
        pnl.loc[pnl.index[i],'n_active']=len(selected)
        
        # 等权持有
        w=1.0/len(selected)
        ret=0
        for k in selected:
            ret+=w*(pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1)
        pnl.loc[pnl.index[i],'pr']=ret
    
    return pnl

def metrics(sr, weekly=52):
    sr=sr.dropna()
    if len(sr)<5: return 0,0,0,0,0
    eq=(1+sr).cumprod()
    y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    # 胜率
    win=(sr>0).mean()
    return cagr, sh, -mdd, win, sr.std()*np.sqrt(weekly)

# ── 多参数回测 ──
print('\n' + '='*70)
print('  多资产动量轮动 + 阈值触发 (2014-2026)')
print('='*70)

# 阈值 = 动量超过多少才入场
thresholds = [-0.05, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

# 先用最优参数(无MA过滤/Top1)扫阈值
print(f'\nTop1 + 6月动量 + 阈值扫描')
print(f'{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Vol%":<8}{"Pos%":<8}{"Ntrade"}')
print('-'*65)

best_cagr,best_thr = 0,0
results=[]
for thr in thresholds:
    p=pnl.copy()
    p=backtest(p, top_k=1, mom='mom6', ma_filter=False, thr=thr)
    cagr,sh,mdd,win,vol=metrics(p['pr'])
    bh_cagr,bh_sh,bh_mdd,_,_=metrics(p['bh'])
    pos_pct=(p['n_active']>0).mean()*100
    active_indices = np.where(p['pr']!=0)[0]
    ntrades = len(active_indices)//2 if len(active_indices)>0 else 0
    # 统计Year/Week切换次数 (信号变化次数)
    signal_changes = (p['n_active'].fillna(0).diff() != 0).sum()
    print(f'{thr:<+8.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd:<8.1f}{win*100:<8.0f}{vol:<8.1f}{pos_pct:<8.0f}{signal_changes:<8}')
    results.append((thr, cagr, sh, -mdd, win*100, vol, pos_pct, signal_changes))
    if cagr > best_cagr:
        best_cagr, best_thr = cagr, thr

best_r = max(results, key=lambda x:x[1])
print(f'\n最优阈值: thr={best_r[0]:+.2f} CAGR={best_r[1]*100:.1f}% Sharpe={best_r[2]:.2f}')

# ── 再扫Top-K + 阈值组合 ──
print(f'\n\nTop-K × 阈值 组合扫描 (mom6, 无MA过滤)')
print(f'{"TopK":<6}{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}{"SignalChg"}')
print('-'*72)

combos=[]
for top_k in [1,2,3]:
    for thr in [-0.05, 0.0, 0.05, 0.10, 0.15, 0.20]:
        p=pnl.copy()
        p=backtest(p, top_k=top_k, mom='mom6', ma_filter=False, thr=thr)
        cagr,sh,mdd,win,vol=metrics(p['pr'])
        sc=(p['n_active'].fillna(0).diff()!=0).sum()
        pos=(p['n_active']>0).mean()*100
        print(f'{top_k:<6}{thr:<+8.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd:<8.1f}{win*100:<8.0f}{pos:<8.0f}{sc:<8}')
        combos.append((top_k, thr, cagr, sh, -mdd, win*100, pos, sc))

print(f'\nBH基准: CAGR={bh_cagr*100:.1f}% Sharpe={bh_sh:.2f} MDD={bh_mdd:.1f}%')
print('\n=== 综合结论 ===')
best_c=max(combos, key=lambda x:x[2])
best_s=max(combos, key=lambda x:x[3])
print(f'最优CAGR: Top{best_c[0]} thr={best_c[1]:+.2f} CAGR={best_c[2]*100:.1f}% Sharpe={best_c[3]:.2f}')
print(f'最优Sharpe: Top{best_s[0]} thr={best_s[1]:+.2f} CAGR={best_s[2]*100:.1f}% Sharpe={best_s[3]:.2f}')
