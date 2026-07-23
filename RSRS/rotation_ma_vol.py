"""均线发散 + 放量 + 动量轮动 多因子策略
指标:
  ma_spread = (MA5 - MA20) / MA20  — 均线发散度
  vol_ratio = volume / MA20_volume  — 量比
  momentum = close / lag(close, 12) - 1  — 6月动量

策略变体:
  A: 纯动量(基准)
  B: 动量 + 均线发散(多头排列才入场)
  C: 动量 + 放量(放量才入场)
  D: 动量 + 均线发散 + 放量 (三因子)
  E: 动量 + 均线发散 OR 放量 (两者满足其一)
"""
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
        return df[['date','close','volume']].dropna().sort_values('date').reset_index(drop=True)
    else:
        df=ak.index_us_stock_sina(symbol=sym)
        df['date']=pd.to_datetime(df['date'])
        return df[['date','close','volume']].dropna().sort_values('date').reset_index(drop=True)

data={}
for k,(s,sym) in indices.items():
    d=load(s,sym)
    if d is not None and len(d)>500:
        data[k]=d

# 周线聚合 (带volume sum)
def to_weekly(df):
    w=df.copy()
    wk=w['date'].dt.isocalendar()
    w['wk_label']=wk['year'].astype(str)+'-W'+wk['week'].astype(str).str.zfill(2)
    ww=w.groupby('wk_label',sort=False).agg({
        'date':'last','close':'last','volume':'sum'
    }).reset_index().sort_values('date')
    ww['date']=pd.to_datetime(ww['date'])
    return ww

weekly={k:to_weekly(v) for k,v in data.items()}

# 构建面板(周线级别)
common=sorted(set.intersection(*[set(weekly[k]['date']) for k in weekly]))
print(f'公用日期: {len(common)}周  {common[0].date()} ~ {common[-1].date()}')

pnl=pd.DataFrame({'date':common})
for k in weekly:
    ww=weekly[k].set_index('date')
    pnl[f'{k}_close']=pnl['date'].map(ww['close'])
    pnl[f'{k}_vol']=pnl['date'].map(ww['volume'])
pnl=pnl.dropna().reset_index(drop=True)

# ─── 计算指标 ───
N=len(pnl)
COL_K=list(indices.keys())

def calc_signals(pnl, mom_period=12):
    """为每个资产计算动量、均线发散、放量信号"""
    pnl2=pnl.copy()
    for k in COL_K:
        c = pnl2[f'{k}_close']
        v = pnl2[f'{k}_vol']
        pnl2[f'{k}_ma5'] = c.rolling(5).mean()
        pnl2[f'{k}_ma10'] = c.rolling(10).mean()
        pnl2[f'{k}_ma20'] = c.rolling(20).mean()
        
        # 均线发散度 = MA5 - MA20 的距离 (归一化)
        pnl2[f'{k}_ma_spread'] = (pnl2[f'{k}_ma5'] / pnl2[f'{k}_ma20'] - 1).fillna(0)
        
        # 多头排列标志 (MA5 > MA10 > MA20)
        pnl2[f'{k}_ma_bull'] = ((pnl2[f'{k}_ma5'] > pnl2[f'{k}_ma10']) & 
                                 (pnl2[f'{k}_ma10'] > pnl2[f'{k}_ma20'])).astype(int)
        
        # 量比 (当前周量 / 20周均量)
        pnl2[f'{k}_vol_ma20'] = v.rolling(20).mean()
        pnl2[f'{k}_vol_ratio'] = (v / pnl2[f'{k}_vol_ma20']).fillna(1.0)
        pnl2[f'{k}_vol_ratio'] = pnl2[f'{k}_vol_ratio'].clip(0, 10)
        
        # 放量标志 (量比 > 阈值)
        pnl2[f'{k}_vol_expand'] = (pnl2[f'{k}_vol_ratio'] > 1.5).astype(int)
        
        # 动量 (6月 = 12周)
        pnl2[f'{k}_mom'] = c.pct_change(mom_period).fillna(0)
    
    return pnl2

pnl = calc_signals(pnl)

# ─── 回测函数 ───
def backtest_combined(pnl, top_k=1, mom_col='_mom', 
                      require_ma_bull=False, require_vol_expand=False,
                      mode='AND', thr=0.0):
    """综合回测
    
    mode: 'AND'=全部满足, 'OR'=任一满足
    require_ma_bull: 是否需要多头排列
    require_vol_expand: 是否需要放量
    """
    pnl['pr']=0.0; pnl['bh']=0.0
    pnl['n_active']=0; pnl['in_market']=0
    
    for i in range(1, N):
        # BH
        bhs=[]; acts=0
        for k in COL_K:
            ret=(pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1)
            bhs.append(ret)
        pnl.loc[pnl.index[i],'bh']=np.mean(bhs)
        
        # 筛选
        cands=[]
        for k in COL_K:
            # 前提: 动量必须可用
            mom_val = pnl[f'{k}{mom_col}'].iloc[i-1]
            if mom_val <= thr:
                continue
            
            ma_bull_ok = True
            vol_ok = True
            if require_ma_bull:
                ma_bull_ok = (pnl[f'{k}_ma_bull'].iloc[i-1] == 1)
            if require_vol_expand:
                vol_ok = (pnl[f'{k}_vol_expand'].iloc[i-1] == 1)
            
            if mode == 'AND':
                ok = ma_bull_ok and vol_ok
            else:  # OR
                # 如果两项都要求，任一满足
                if require_ma_bull and require_vol_expand:
                    ok = ma_bull_ok or vol_ok
                elif require_ma_bull:
                    ok = ma_bull_ok
                elif require_vol_expand:
                    ok = vol_ok
                else:
                    ok = True
            
            if ok:
                cands.append((k, mom_val))
        
        if not cands:
            pnl.loc[pnl.index[i],'pr']=0; pnl.loc[pnl.index[i],'n_active']=0
            continue
        
        cands.sort(key=lambda x:-x[1])
        selected=[c[0] for c in cands[:top_k]]
        w=1.0/len(selected)
        ret=0
        for k in selected:
            ret+=w*(pnl[f'{k}_close'].iloc[i]/pnl[f'{k}_close'].iloc[i-1]-1)
        pnl.loc[pnl.index[i],'pr']=ret
        pnl.loc[pnl.index[i],'n_active']=len(selected)
    
    return pnl

def metrics(sr, weekly=52):
    sr=sr.dropna()
    if len(sr)<5: return 0,0,0,0,0,0
    eq=(1+sr).cumprod()
    y=len(sr)/weekly
    cagr=eq.iloc[-1]**(1/y)-1 if y>0 else 0
    sh=np.sqrt(weekly)*sr.mean()/sr.std() if sr.std()>1e-10 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()
    win=(sr>0).mean()
    vol_ann=sr.std()*np.sqrt(weekly)
    return cagr, sh, mdd, win, vol_ann, (sr!=0).mean()

# 获取BH基准
p0=pnl.copy()
p0=backtest_combined(p0, mode='AND')
bh_cagr,bh_sh,bh_mdd,_,_,_=metrics(p0['bh'])
print(f'\nBH基准: CAGR={bh_cagr*100:.1f}% Sharpe={bh_sh:.2f} MDD={bh_mdd*100:.1f}%')

# ─── 多因子扫描 ───
print(f'\n{"="*80}')
print(f'  均线发散 + 放量 + 动量轮动 因子扫描')
print(f'{"="*80}')

configs = []
# 基准变体
for req_ma in [False, True]:
    for req_vol in [False, True]:
        if not(req_ma or req_vol):
            configs.append(('基准动量', req_ma, req_vol, 'AND'))
        elif req_ma and not req_vol:
            configs.append(('动量+均线发散', req_ma, req_vol, 'AND'))
        elif not req_ma and req_vol:
            configs.append(('动量+放量', req_ma, req_vol, 'AND'))
        else:
            configs.append(('三因子AND', req_ma, req_vol, 'AND'))
            configs.append(('三因子OR', req_ma, req_vol, 'OR'))

# 不同动量周期 + 阈值
results = []
for mom_pd in [6, 12, 24]:  # 3月/6月/12月周
    col = f'_mom' if mom_pd==12 else f'_mom{mom_pd}'
    # 先重新计算动量
    if mom_pd != 12:
        pnl_mom = pnl.copy()
        for k in COL_K:
            pnl_mom[f'{k}_mom{mom_pd}'] = pnl_mom[f'{k}_close'].pct_change(mom_pd).fillna(0)
    else:
        pnl_mom = pnl
    
    for name, req_ma, req_vol, mode in configs:
        for thr in [0.0, 0.05, 0.10]:
            if thr > 0 and thr != 0.05:
                continue  # 仅测试0和0.05
            
            p = pnl_mom.copy()
            momc = f'_mom{mom_pd}' if mom_pd != 12 else '_mom'
            p = backtest_combined(p, top_k=1, mom_col=momc,
                                  require_ma_bull=req_ma, require_vol_expand=req_vol,
                                  mode=mode, thr=thr)
            cagr, sh, mdd, win, vol_ann, pos_pct = metrics(p['pr'])
            label = f'{name}|mom{mom_pd}w|thr{thr:+.0%}'
            results.append((label, name, mom_pd, thr, req_ma, req_vol, mode, cagr, sh, mdd, win, pos_pct))

# 输出
print(f'\n{"标签":<35}{"CAGR%":<8}{"Sharpe":<8}{"MDD%":<8}{"Win%":<8}{"Pos%":<8}')
print('-'*75)
results.sort(key=lambda x:-x[7])
for r in results[:20]:
    print(f'{r[0]:<35}{r[7]*100:<8.1f}{r[8]:<8.2f}{r[9]*100:<8.1f}{r[10]*100:<8.0f}{r[11]*100:<8.0f}')

print(f'\n基准 BH: CAGR={bh_cagr*100:.1f}% Sharpe={bh_sh:.2f}')

# ─── 提取关键发现 ───
print('\n' + '='*80)
print('  KEY FINDINGS')
print('='*80)

best_c = results[0]
print(f'全体最优: {best_c[0]} CAGR={best_c[7]*100:.1f}% Sharpe={best_c[8]:.2f} MDD={best_c[9]*100:.1f}%')

print('\n--- 按因子分组 ---')
for grp in ['基准动量','动量+均线发散','动量+放量','三因子AND','三因子OR']:
    grp_r = [r for r in results if r[1] == grp]
    if grp_r:
        best_g = max(grp_r, key=lambda x:x[7])
        print(f'{grp:<16}: 最优 CAGR={best_g[7]*100:5.1f}% Sharpe={best_g[8]:.2f} ({best_g[0]})')
