"""放量三种用法测试：
1. 降低放量阈值 (1.0-2.0 扫描)
2. 放量作出场条件 (缩量卖出)
3. 放量作权重调整
"""
import akshare as ak
import numpy as np, pandas as pd
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
        return df[['date','close','volume']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close','volume']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(s,sym) in indices.items():
    d=load(s,sym)
    if d is not None and len(d)>500: data[k]=d

# 周线
def to_weekly(df):
    w=df.copy()
    wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label',sort=False).agg({'date':'last','close':'last','volume':'sum'}).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date'])
    return ww

weekly={k:to_weekly(v) for k,v in data.items()}
common=sorted(set.intersection(*[set(weekly[k]['date']) for k in weekly]))

pnl=pd.DataFrame({'date':common})
for k in weekly:
    ww=weekly[k].set_index('date')
    pnl[f'{k}_close']=pnl['date'].map(ww['close'])
    pnl[f'{k}_vol']=pnl['date'].map(ww['volume'])
pnl=pnl.dropna().reset_index(drop=True)

N=len(pnl); COL_K=list(indices.keys())

# 计算所有指标
for k in COL_K:
    c=pnl[f'{k}_close']; v=pnl[f'{k}_vol']
    pnl[f'{k}_ma20']=c.rolling(20).mean()
    pnl[f'{k}_vol_ma20']=v.rolling(20).mean()
    pnl[f'{k}_vol_ratio']=(v/pnl[f'{k}_vol_ma20']).fillna(1.0).clip(0,10)
    pnl[f'{k}_vol_shrink']=(pnl[f'{k}_vol_ratio']<0.7).astype(int)  # 缩量30%
    pnl[f'{k}_mom6']=c.pct_change(6).fillna(0)  # 3月动量
    pnl[f'{k}_mom12']=c.pct_change(12).fillna(0)  # 6月动量

def metrics(sr, weekly=52):
    sr=sr.dropna()
    if len(sr)<5: return 0,0,0,0,0,0
    eq=(1+sr).cumprod()
    y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean(); vol_ann=sr.std()*np.sqrt(weekly)
    return cagr,sh,mdd,win,vol_ann,(sr!=0).mean()

# ─── 方向1: 降低放量阈值扫描 ───
print('='*80)
print('  方向1: 不同放量阈值 + 动量6w + thr5%')
print('='*80)

bh_cagr,bh_sh,bh_mdd,_,_,_=metrics(pnl[[f'{k}_close' for k in COL_K]].pct_change().mean(axis=1))
print(f'BH基准: CAGR={bh_cagr*100:.1f}% Sharpe={bh_sh:.2f} MDD={bh_mdd*100:.1f}%')
print(f'\n{"VolThr":<10}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}{"Ntrade"}' )
print('-'*62)

vol_results=[]
for vol_thr in [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]:
    p=pnl.copy()
    p['pr']=0.0; p['n_active']=0
    for i in range(1,N):
        cands=[]
        for k in COL_K:
            mom_val=p[f'{k}_mom6'].iloc[i-1]
            if mom_val <= 0.05: continue
            vol_ratio=p[f'{k}_vol_ratio'].iloc[i-1]
            if vol_ratio < vol_thr: continue
            cands.append((k, mom_val))
        if cands:
            cands.sort(key=lambda x:-x[1])
            sel=[c[0] for c in cands[:1]]
            w=1.0/len(sel)
            ret=sum(w*(p[f'{s}_close'].iloc[i]/p[f'{s}_close'].iloc[i-1]-1) for s in sel)
            p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'n_active']=len(sel)
    cagr,sh,mdd,win,_,pos=metrics(p['pr'])
    sc=(p['n_active'].diff()!=0).sum()
    print(f'{vol_thr:<10.1f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{win*100:<8.0f}{pos*100:<8.0f}{sc:<8}')
    vol_results.append((vol_thr, cagr, sh, -mdd, pos*100))

# ─── 方向2: 缩量出场 ───
print(f'\n{"="*80}')
print(f'  方向2: 缩量(v<0.7MA)出场')
print(f'{"="*80}')
print(f'\n{"Thr":<8}{"MOM":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*62)

exit_results=[]
for thr in [0.0, 0.03, 0.05]:
    for mom_pd in [6,12]:
        p=pnl.copy()
        momc=f'_mom{mom_pd}'
        p['pr']=0.0; p['n_active']=0; p['current_hold']=0
        for i in range(1,N):
            # 正常轮动
            cands=[]
            for k in COL_K:
                m=p[f'{k}{momc}'].iloc[i-1]
                if m <= thr: continue
                cands.append((k,m))
            if cands:
                cands.sort(key=lambda x:-x[1])
                # 检查Top1是否缩量
                top1=cands[0][0]
                vol_shrink=(p[f'{top1}_vol_ratio'].iloc[i-1]<0.7)
                if vol_shrink:
                    p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'n_active']=0
                else:
                    ret=p[f'{top1}_close'].iloc[i]/p[f'{top1}_close'].iloc[i-1]-1
                    p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'n_active']=1
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'n_active']=0
        
        cagr,sh,mdd,win,_,pos=metrics(p['pr'])
        print(f'{thr:<+8.2f}{f"mom{mom_pd}w":<8}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{win*100:<8.0f}{pos*100:<8.0f}')
        exit_results.append((thr, mom_pd, cagr, sh, -mdd, pos*100))

# ─── 方向3: 放量权重调整 ───
print(f'\n{"="*80}')
print(f'  方向3: 放量作权重调整 / 复合放量因子')
print(f'{"="*80}')

# 方式3a: 动量×放量 复合因子 (二者相乘排秩)
print(f'\n--- 3a: 动量×放量复合因子排名 ---')
print(f'{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*56)

weight_results_3a=[]
for thr in [0.0, 0.03, 0.05]:
    p=pnl.copy()
    p['pr']=0.0; p['n_active']=0
    for i in range(1,N):
        cands=[]
        for k in COL_K:
            m=p[f'{k}_mom6'].iloc[i-1]
            if m <= thr: continue
            vr=p[f'{k}_vol_ratio'].iloc[i-1]
            score=m*vr  # 复合得分 = 动量 × 量比
            cands.append((k, score))
        if cands:
            cands.sort(key=lambda x:-x[1])
            sel=[c[0] for c in cands[:1]]
            w=1.0/len(sel)
            ret=sum(w*(p[f'{s}_close'].iloc[i]/p[f'{s}_close'].iloc[i-1]-1) for s in sel)
            p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'n_active']=len(sel)
    cagr,sh,mdd,win,_,pos=metrics(p['pr'])
    print(f'{thr:<+8.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{win*100:<8.0f}{pos*100:<8.0f}')
    weight_results_3a.append((thr, cagr, sh, -mdd, pos*100))

# 方式3b: 放量动量择时切换：放量时用3月动量，缩量时用12月动量
print(f'\n--- 3b: 放量=3月动量, 缩量=12月动量 ---')
print(f'{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*56)

for thr in [0.0, 0.05]:
    p=pnl.copy()
    p['pr']=0.0; p['n_active']=0
    for i in range(1,N):
        cands=[]
        for k in COL_K:
            vr=p[f'{k}_vol_ratio'].iloc[i-1]
            # 放量用mom6, 缩量用mom12
            momc = '_mom6' if vr >= 1.2 else '_mom12'
            m=p[f'{k}{momc}'].iloc[i-1]
            if m <= thr: continue
            cands.append((k,m))
        if cands:
            cands.sort(key=lambda x:-x[1])
            sel=[c[0] for c in cands[:1]]
            w=1.0/len(sel)
            ret=sum(w*(p[f'{s}_close'].iloc[i]/p[f'{s}_close'].iloc[i-1]-1) for s in sel)
            p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'n_active']=len(sel)
    cagr,sh,mdd,win,_,pos=metrics(p['pr'])
    print(f'{thr:<+8.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{win*100:<8.0f}{pos*100:<8.0f}')

# 方式3c: 动量排名 + 反向量比排名（缩量更好）
print(f'\n--- 3c: 缩量过滤（反向量比, 量大减分） ---')
print(f'{"Thr":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*56)

for thr in [0.0, 0.05]:
    p=pnl.copy()
    p['pr']=0.0; p['n_active']=0
    for i in range(1,N):
        cands=[]
        for k in COL_K:
            m=p[f'{k}_mom6'].iloc[i-1]
            if m <= thr: continue
            vr=p[f'{k}_vol_ratio'].iloc[i-1]
            # 缩量加分 (vr<0.7), 极大量减分 (vr>2.5)
            vol_penalty = 0.0
            if vr > 2.5: vol_penalty = -0.10
            elif vr < 0.7: vol_penalty = 0.05
            elif vr < 1.0: vol_penalty = 0.02
            score = m + vol_penalty
            cands.append((k, score))
        if cands:
            cands.sort(key=lambda x:-x[1])
            sel=[c[0] for c in cands[:1]]
            w=1.0/len(sel)
            ret=sum(w*(p[f'{s}_close'].iloc[i]/p[f'{s}_close'].iloc[i-1]-1) for s in sel)
            p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'n_active']=len(sel)
    cagr,sh,mdd,win,_,pos=metrics(p['pr'])
    print(f'{thr:<+8.2f}{cagr*100:<8.1f}{sh:<8.2f}{-mdd*100:<8.1f}{win*100:<8.0f}{pos*100:<8.0f}')

# ─── 纯动量基准(汇总) ───
print(f'\n{"="*80}')
print(f'  汇总对比')
print(f'{"="*80}')
print(f'\n基准: 纯动量6w+thr5% — CAGR=16.3% Sharpe=0.77 MDD=-39.6%')
best_1 = max(vol_results, key=lambda x:x[1]) if vol_results else None
if best_1: print(f'方向1最佳: vol>{best_1[0]:.1f} CAGR={best_1[1]*100:.1f}% Sharpe={best_1[2]:.2f} MDD={best_1[3]:.1f}%')
best_2 = max(exit_results, key=lambda x:x[2]) if exit_results else None
if best_2: print(f'方向2最佳: thr{best_2[0]:+.2f} mom{best_2[1]}w CAGR={best_2[2]*100:.1f}% Sharpe={best_2[3]:.2f} MDD={best_2[4]:.1f}%')
best_3a = max(weight_results_3a, key=lambda x:x[1]) if weight_results_3a else None
if best_3a: print(f'方向3a最佳: thr{best_3a[0]:+.2f} CAGR={best_3a[1]*100:.1f}% Sharpe={best_3a[2]:.2f} MDD={best_3a[3]:.1f}%')
