"""动量轮动 全参数扫描: 动量周期×调仓频率×阈值
目标: 找到CAGR/Sharpe最优组合
"""
import akshare as ak
import numpy as np, pandas as pd, itertools
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
        df=ak.stock_zh_index_daily(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(s,sym) in indices.items():
    d=load(s,sym)
    if d is not None and len(d)>500: data[k]=d

# 转周线
def to_weekly(df):
    w=df.copy(); wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label',sort=False).agg({'date':'last','close':'last'}).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date'])
    return ww

weekly={k:to_weekly(v) for k,v in data.items()}
common=sorted(set.intersection(*[set(weekly[k]['date']) for k in weekly]))

pnl=pd.DataFrame({'date':common})
for k in weekly:
    ww=weekly[k].set_index('date')
    pnl[f'{k}_close']=pnl['date'].map(ww['close'])
pnl=pnl.dropna().reset_index(drop=True); N=len(pnl)
COL_K=list(indices.keys())
print(f'面板: {N}周, {len(COL_K)}资产, {common[0].date()}~{common[-1].date()}')

def metrics(sr,weekly=52):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean(); return cagr,sh,mdd,win

# BH
bhs=[]; 
for i in range(1,N):
    bhs.append(np.mean([pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1 for k in COL_K]))
bh=pd.Series(bhs)
bh_c,bh_s,bh_m,bh_w=metrics(bh)
print(f'BH: CAGR={bh_c*100:.1f}% Sharpe={bh_s:.2f} MDD={bh_m*100:.1f}%')

# ─── 全参数扫描 ───
mom_periods = [4, 6, 8, 12, 16, 24]      # 动量窗口(周)=2月~12月
rebal_freqs = [1, 2, 4, 6, 8, 12]        # 调仓频率(周)
thresholds = [0.0, 0.03, 0.05, 0.08, 0.10]

total=len(mom_periods)*len(rebal_freqs)*len(thresholds)
print(f'\n扫描: {len(mom_periods)}×{len(rebal_freqs)}×{len(thresholds)}={total} 组合')
print(f'{"Mom":<6}{"Rebal":<6}{"Thr":<6}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*60)

results=[]
for mom_pd in mom_periods:
    # 预计算动量
    pnl_mom = pnl.copy()
    for k in COL_K:
        pnl_mom[f'{k}_mom'] = pnl_mom[f'{k}_close'].pct_change(mom_pd).fillna(0)
    
    for rb in rebal_freqs:
        for thr in thresholds:
            p = pnl_mom.copy()
            p['pr']=0.0; p['cat']=0; p['hold']=''
            
            for i in range(1,N):
                # 调仓日判定
                is_rebal = (i % rb) == 1 or i == 1
                
                if is_rebal:
                    # 调仓日: 重新选标的
                    cands=[]
                    for k in COL_K:
                        m=p[f'{k}_mom'].iloc[i-1]
                        if m <= thr: continue
                        cands.append((k,m))
                    
                    if not cands:
                        p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'hold']=''
                        continue
                    
                    cands.sort(key=lambda x:-x[1])
                    sel=[c[0] for c in cands[:1]]
                    hold_asset = sel[0]
                    w=1.0/len(sel)
                    ret=sum(w*(p[f'{s}_close'].iloc[i]/p[f'{s}_close'].iloc[i-1]-1) for s in sel)
                    p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'cat']=len(sel)
                    p.loc[p.index[i],'hold']=hold_asset
                else:
                    # 非调仓日: 继续持有同一标的，计算真实收益
                    hold_asset = p['hold'].iloc[i-1]
                    if hold_asset:
                        ret = p[f'{hold_asset}_close'].iloc[i]/p[f'{hold_asset}_close'].iloc[i-1]-1
                        p.loc[p.index[i],'pr']=ret
                        p.loc[p.index[i],'cat']=p['cat'].iloc[i-1]
                        p.loc[p.index[i],'hold']=hold_asset
                    else:
                        p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0
            
            cagr,sh,mdd,win=metrics(p['pr'])
            pos_pct=(p['cat']>0).mean()*100
            # 信号变化次数
            sig_chg=(p['cat'].fillna(0).diff()!=0).sum()
            results.append((mom_pd, rb, thr, cagr, sh, -mdd, win, pos_pct, sig_chg))

# 排序输出
results.sort(key=lambda x:-x[3])  # by CAGR

print(f'\nTop 15 by CAGR:')
print(f'{"Mom(w)":<8}{"Reb(w)":<8}{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}{"SigChg":<8}')
print('-'*72)
for r in results[:15]:
    print(f'{r[0]:<8}{r[1]:<8}{r[2]:<+8.2f}{r[3]*100:<8.1f}{r[4]:<8.2f}{r[5]:<8.1f}{r[6]*100:<8.0f}{r[7]:<8.0f}{r[8]:<8}')

print(f'\nTop 10 by Sharpe:')
results_by_sh=sorted(results, key=lambda x:-x[4])
for r in results_by_sh[:10]:
    print(f'Mom={r[0]:>2}w ReB={r[1]:>2}w Thr={r[2]:+.0%} C={r[3]*100:.1f}% S={r[4]:.2f} MDD={r[5]:.1f}% Win={r[6]*100:.0f}% Pos={r[7]:.0f}% Chg={r[8]}')

# 最优
best_c=max(results, key=lambda x:x[3])
best_s=max(results, key=lambda x:x[4])
print(f'\n🏆 最优CAGR: Mom={best_c[0]}w Rebal={best_c[1]}w Thr={best_c[2]:+.0%} CAGR={best_c[3]*100:.1f}% Sharpe={best_c[4]:.2f} MDD={best_c[5]:.1f}%')
print(f'🏆 最优Sharpe: Mom={best_s[0]}w Rebal={best_s[1]}w Thr={best_s[2]:+.0%} CAGR={best_s[3]*100:.1f}% Sharpe={best_s[4]:.2f} MDD={best_s[5]:.1f}%')
