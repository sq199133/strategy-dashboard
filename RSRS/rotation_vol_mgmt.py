"""波动率仓位管理 — 多资产动量轮动优化
在 Mom=4w + Rebal=2w + Thr=5% + Top1 基础上加:
- 波动率缩放: 目标波动率 / 滚动实际波动率
- 扫描 VW(窗口) × TVol(目标)
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
        df=ak.stock_zh_index_daily(symbol=sym); df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym); df['date']=pd.to_datetime(df['date'])
        return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(s,sym) in indices.items():
    d=load(s,sym)
    if d is not None and len(d)>500: data[k]=d

def to_weekly(df):
    w=df.copy(); wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label',sort=False).agg({'date':'last','close':'last'}).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date']); return ww

weekly={k:to_weekly(v) for k,v in data.items()}
common=sorted(set.intersection(*[set(weekly[k]['date']) for k in weekly]))
pnl=pd.DataFrame({'date':common})
for k in weekly:
    ww=weekly[k].set_index('date')
    pnl[f'{k}_close']=pnl['date'].map(ww['close'])
pnl=pnl.dropna().reset_index(drop=True); N=len(pnl)
COL_K=list(indices.keys())
print(f'面板: {N}周, {len(COL_K)}资产, {common[0].date()}~{common[-1].date()}')

for k in COL_K:
    pnl[f'{k}_mom4'] = pnl[f'{k}_close'].pct_change(4).fillna(0)  # 4周=2月动量

def metrics(sr, weekly=52):
    sr=sr.dropna(); eq=(1+sr).cumprod(); y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean(); return cagr,sh,mdd,win

# BH
bhs=[np.mean([pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1 for k in COL_K]) for i in range(1,N)]
bh_c,bh_s,bh_m,bh_w=metrics(pd.Series(bhs))
print(f'BH: CAGR={bh_c*100:.1f}% Sharpe={bh_s:.2f} MDD={-bh_m*100:.1f}%\n')

# ─── 基线: 无波动率管理 ───
def run_base(pnl, thr=0.05, rebal=2):
    p=pnl.copy(); p['pr']=0.0; p['cat']=0; p['hold']=''
    for i in range(1,N):
        is_rb = (i % rebal)==1
        if is_rb:
            cands=[(k,p[f'{k}_mom4'].iloc[i-1]) for k in COL_K if p[f'{k}_mom4'].iloc[i-1] > thr]
            if cands:
                best=max(cands, key=lambda x:x[1])[0]
                ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=best
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'hold']=''
        else:
            h=p['hold'].iloc[i-1]
            if h:
                ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                p.loc[p.index[i],'pr']=ret; p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=h
            else:
                p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0
    return p

base=run_base(pnl)
bc,bs,bm,bw=metrics(base['pr'])
bpos=(base['cat']>0).mean()*100
print(f'基线: CAGR={bc*100:.1f}% Sharpe={bs:.2f} MDD={-bm*100:.1f}% Pos={bpos:.0f}%')

# ─── 波动率管理回测 ───
# 仓位 = max(0, min(1, target_vol / rolling_vol))
# rolling_vol 用 portfolio 自身周收益率的滚动标准差 * sqrt(52) = 年化
# 缩放因子应用到 h 仓位

vol_windows = [4, 8, 12, 24, 36, 52]   # 波动率窗口(周)=1月~1年
target_vols = [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25]  # 目标年化波动率

print(f'\n波动率管理扫描: {len(vol_windows)}×{len(target_vols)}={len(vol_windows)*len(target_vols)} 组合')
print(f'\n{"VW(w)":<8}{"TVol":<8}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}{"AvgWgt":<8}{"Scale<0.5":<8}')
print('-'*72)

vol_results=[]
for vw in vol_windows:
    for tv in target_vols:
        p = pnl.copy()
        p['pr']=0.0; p['cat']=0; p['hold']=''; p['weight']=1.0
        
        # 预计算波动率缩放因子
        # 用等权组合周收益的滚动std
        p['port_ret'] = p[[f'{k}_close' for k in COL_K]].pct_change().mean(axis=1)
        p['rolling_vol'] = p['port_ret'].rolling(vw).std() * np.sqrt(52)
        p['scale'] = p.apply(lambda r: min(1.0, tv / max(r['rolling_vol'], 0.01)) if not pd.isna(r['rolling_vol']) else 1.0, axis=1)
        
        for i in range(1,N):
            is_rb = (i % 2)==1
            scaler = p['scale'].iloc[i-1]
            
            if is_rb:
                cands=[(k,p[f'{k}_mom4'].iloc[i-1]) for k in COL_K if p[f'{k}_mom4'].iloc[i-1] > 0.05]
                if cands:
                    best=max(cands, key=lambda x:x[1])[0]
                    ret=p[f'{best}_close'].iloc[i]/p[f'{best}_close'].iloc[i-1]-1
                    p.loc[p.index[i],'pr']=ret*scaler
                    p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=best; p.loc[p.index[i],'weight']=scaler
                else:
                    p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'weight']=0; p.loc[p.index[i],'hold']=''
            else:
                h=p['hold'].iloc[i-1]
                wgt=p['weight'].iloc[i-1]
                if h:
                    ret=p[f'{h}_close'].iloc[i]/p[f'{h}_close'].iloc[i-1]-1
                    p.loc[p.index[i],'pr']=ret*wgt
                    p.loc[p.index[i],'cat']=1; p.loc[p.index[i],'hold']=h; p.loc[p.index[i],'weight']=wgt
                else:
                    p.loc[p.index[i],'pr']=0; p.loc[p.index[i],'cat']=0; p.loc[p.index[i],'weight']=0
        
        cagr,sh,mdd,win=metrics(p['pr'])
        pos=(p['cat']>0).mean()*100
        avg_wgt=p['weight'].mean()*100
        low_scale=(p['scale']<0.5).mean()*100
        vol_results.append((vw,tv,cagr,sh,-mdd,win,pos,avg_wgt,low_scale))

vol_results.sort(key=lambda x:-x[2])
print(f'\nTop 10 by CAGR:')
for r in vol_results[:10]:
    print(f'{r[0]:<8}{r[1]:<8.2f}{r[2]*100:<8.1f}{r[3]:<8.2f}{r[4]:<8.1f}{r[5]*100:<8.0f}{r[6]:<8.0f}{r[7]:<8.0f}{r[8]:<8.0f}')

print(f'\nTop 10 by Sharpe:')
vol_by_sh=sorted(vol_results, key=lambda x:-x[3])
for r in vol_by_sh[:10]:
    print(f'VW={r[0]}w TVol={r[1]:.2f} C={r[2]*100:.1f}% S={r[3]:.2f} MDD={r[4]:.1f}% Win={r[5]*100:.0f}% Pos={r[6]:.0f}% Wgt={r[7]:.0f}%')

best_c=max(vol_results, key=lambda x:x[2])
best_s=max(vol_results, key=lambda x:x[3])
print(f'\n🏆 最优CAGR: VW={best_c[0]}w TVol={best_c[1]:.2f} CAGR={best_c[2]*100:.1f}% Sharpe={best_c[3]:.2f} MDD={best_c[4]:.1f}%')
print(f'🏆 最优Sharpe: VW={best_s[0]}w TVol={best_s[1]:.2f} CAGR={best_s[2]*100:.1f}% Sharpe={best_s[3]:.2f} MDD={best_s[4]:.1f}%')
print(f'\n基线(无波动率): CAGR={bc*100:.1f}% Sharpe={bs:.2f} MDD={-bm*100:.1f}%')
