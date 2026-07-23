"""
指数级20周均线趋势跟踪
使用AKShare直接拉指数数据(非ETF)，干净可靠
"""
import akshare as ak
import numpy as np, pandas as pd
warnings = __import__('warnings'); warnings.filterwarnings('ignore')

# ─── 1. 指数池定义 ───
INDICES = {
    # A股
    'CN300':  ('stock_zh_index_daily', 'sh000300', '沪深300'),
    'CN50':   ('stock_zh_index_daily', 'sh000016', '上证50'),
    'CN500':  ('stock_zh_index_daily', 'sh000905', '中证500'),
    'CN1000': ('stock_zh_index_daily', 'sh000852', '中证1000'),
    'CYB':    ('stock_zh_index_daily', 'sz399006', '创业板'),
    'KCB':    ('stock_zh_index_daily', 'sh000688', '科创50'),
    # 美股
    'SP500':  ('us_sina', '.INX', '标普500'),
    'NASDAQ': ('us_sina', '.IXIC', '纳斯达克'),
    'NDX100': ('us_sina', '.NDX', '纳指100'),
    'DJI':    ('us_sina', '.DJI', '道琼斯'),
    # 港股
    'HSI':    ('hk_sina', 'HSI', '恒生指数'),
}

def load_index(source, symbol, name):
    """统一加载指数数据"""
    try:
        if source == 'stock_zh_index_daily':
            df = ak.stock_zh_index_daily(symbol=symbol)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
        elif source == 'us_sina':
            df = ak.index_us_stock_sina(symbol=symbol)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
        elif source == 'hk_sina':
            df = ak.stock_hk_index_daily_sina(symbol=symbol)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f'  ❌ {name}: {str(e)[:80]}')
        return None

def to_weekly(df):
    w=df.copy(); w['wk']=w['date'].dt.isocalendar().year.astype(str)+'-W'+w['date'].dt.isocalendar().week.astype(str).str.zfill(2)
    return w.groupby('wk').agg({'date':'last','close':'last'}).reset_index(drop=True).sort_values('date')

# ─── 2. 加载全部数据 ───
print('加载指数数据...')
data = {}
for key, (src, sym, name) in INDICES.items():
    df = load_index(src, sym, name)
    if df is not None and len(df) >= 200:
        data[key] = df
        print(f'  ✅ {name:<10}({key:<8}): {len(df):>5}行  {df.iloc[0]["date"].date()} ~ {df.iloc[-1]["date"].date()}')

# ─── 3. 构建周线面板 ───
print(f'\n转换周线...')
weekly = {}
for key, df in data.items():
    wk = to_weekly(df)
    weekly[key] = wk

# 找公共周（按池分组）
groups = {
    '全部': list(weekly.keys()),
    'A股+美股': [k for k in weekly if k.startswith('CN') or k.startswith(('SP','NASDAQ','NDX'))],
    '纯A股': [k for k in weekly if k.startswith('CN')],
    '纯美股': [k for k in weekly if k.startswith(('SP','NASDAQ','NDX','DJI'))],
}

for gname, keys in groups.items():
    common = sorted(set.intersection(*[set(weekly[k]['date']) for k in keys if k in weekly]))
    if not common: 
        print(f'  ⚠ {gname}: 无公共日期')
        continue
    print(f'  {gname:<10}({len(keys)}只): {len(common)}周  {common[0].date()} ~ {common[-1].date()}')

# ─── 4. 回测函数 ───
def build_panel(keys):
    """构建周线面板"""
    common = sorted(set.intersection(*[set(weekly[k]['date']) for k in keys]))
    panel = pd.DataFrame({'date': common}).set_index('date')
    for k in keys:
        panel[k] = panel.index.map(weekly[k].set_index('date')['close'])
        panel[f'ma20_{k}'] = panel[k].rolling(20).mean()
    return panel

def backtest_ma20(panel, keys, X):
    """周线20均线策略, X=连续确认周数"""
    for k in keys:
        above = (panel[k] > panel[f'ma20_{k}']).astype(int)
        above_x = above.rolling(X, min_periods=X).sum()
        below = (panel[k] <= panel[f'ma20_{k}']).astype(int)
        below_x = below.rolling(X, min_periods=X).sum()
        
        pos = np.zeros(len(panel)); inp = False
        for i in range(len(panel)):
            if above_x.iloc[i] == X and not inp: inp = True
            if below_x.iloc[i] == X and inp: inp = False
            pos[i] = 1 if inp else 0
        panel[f'pos_{k}'] = pos
        panel[f'ret_{k}'] = panel[k].pct_change().fillna(0)
    
    # 等权组合
    n_pos = panel[[f'pos_{k}' for k in keys]].sum(axis=1)
    panel['w'] = n_pos.apply(lambda x: 1/x if x > 0 else 0)
    panel['pr'] = sum(panel[f'ret_{k}'] * panel[f'pos_{k}'].shift(1).fillna(0) * panel['w'] for k in keys)
    
    # BH
    panel['bh'] = panel[[f'ret_{k}' for k in keys]].mean(axis=1)
    
    return panel

def metrics(pr, weekly=52):
    sr = pr.dropna()
    if len(sr) < 10: return 0, 0, 0
    eq = (1 + sr).cumprod()
    y = len(sr) / weekly
    cagr = eq.iloc[-1] ** (1/y) - 1 if y > 0 else 0
    sh = np.sqrt(weekly) * sr.mean() / sr.std() if sr.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    return cagr, sh, mdd

def count_trades(panel, keys):
    tr = 0
    for k in keys:
        p = panel[f'pos_{k}'].values
        for i in range(1, len(p)):
            if p[i] == 1 and p[i-1] == 0: tr += 1
    return tr

# ─── 5. 回测各池各X值 ───
print('\n' + '='*70)
print('  周线20均线策略回测')
print('='*70)

for gname, keys in groups.items():
    if len(keys) < 2: continue
    panel = build_panel(keys)
    print(f'\n── {gname} ({len(keys)}只, {len(panel)}周) ──')
    print(f'{"X":<5}{"CAGR%":<9}{"Sharpe":<9}{"MDD%":<9}{"BH%":<9}{"交易":<7}{"持仓%":<7}')
    print('-'*55)
    for X in [1,2,3,4,5]:
        p = panel.copy()
        p = backtest_ma20(p, keys, X)
        cagr, sh, mdd = metrics(p['pr'])
        _, _, bh_mdd = metrics(p['bh'])
        bh_cagr, bh_sh, _ = metrics(p['bh'])
        tr = count_trades(p, keys)
        pos_pct = (p[[f'pos_{k}' for k in keys]].sum(axis=1) > 0).sum() / len(p) * 100
        print(f'{X:<5}{cagr*100:<9.1f}{sh:<9.2f}{-mdd*100:<9.1f}{bh_cagr*100:<9.1f}{tr:<7}{pos_pct:<7.1f}')
