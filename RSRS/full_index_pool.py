"""数据整备完成，构建完整资产池"""
import akshare as ak
import numpy as np, pandas as pd
from datetime import datetime

# ─── 资产池定义 ───
ASSETS = {
    # A股宽基
    'CN50':   ('stock_zh_index_daily', 'sh000016', '上证50'),
    'CN300':  ('stock_zh_index_daily', 'sh000300', '沪深300'),
    'CN500':  ('stock_zh_index_daily', 'sh000905', '中证500'),
    'CN1000': ('stock_zh_index_daily', 'sh000852', '中证1000'),
    'CN2000': ('stock_zh_index_daily', 'sh000932', '中证2000'),
    'CYB':    ('stock_zh_index_daily', 'sz399006', '创业板指'),
    'KCB50':  ('stock_zh_index_daily', 'sh000688', '科创50'),
    # 美股宽基
    'SP500':  ('us_sina', '.INX', '标普500'),
    'NASDAQ': ('us_sina', '.IXIC', '纳斯达克'),
    'DJI':    ('us_sina', '.DJI', '道琼斯'),
    # 商品
    'COMM':   ('stock_zh_index_daily', 'sh000066', '上证商品'),
}

def load(src, sym, name):
    try:
        if src == 'stock_zh_index_daily':
            df = ak.stock_zh_index_daily(symbol=sym)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
        elif src == 'us_sina':
            df = ak.index_us_stock_sina(symbol=sym)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date','close']].dropna().sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f'  ❌ {name}: {str(e)[:80]}')
        return None

# 加载
data = {}
for key, (src, sym, name) in ASSETS.items():
    df = load(src, sym, name)
    if df is not None and len(df) >= 200:
        data[key] = df
        print(f'  ✅ {name:<10}({key:<8}): {len(df):>5}行 {df.iloc[0]["date"].date()} ~ {df.iloc[-1]["date"].date()}')

# ─── 周线转换 ───
def to_weekly(df):
    w = df.copy()
    wk = w['date'].dt.isocalendar()
    w['wk'] = wk['year'].astype(str) + '-W' + wk['week'].astype(str).str.zfill(2)
    return w.groupby('wk').agg({'date':'last','close':'last'}).reset_index(drop=True).sort_values('date')

weekly = {k: to_weekly(v) for k,v in data.items()}

# ─── 分组公共日期 ───
groups = {
    '全部A股': [k for k in weekly if k.startswith('CN')],
    '纯美股': [k for k in weekly if k.startswith(('SP','NASDAQ','DJI'))],
    'A股+美股': [k for k in weekly if k.startswith('CN') or k.startswith(('SP','NASDAQ','DJI'))],
    '全资产(含商品)': list(weekly.keys()),
}

print('\n=== 分组公共日期 ===')
for gname, keys in groups.items():
    common = sorted(set.intersection(*[set(weekly[k]['date']) for k in keys]))
    print(f'{gname:<16}({len(keys)}只): {len(common)}周 {common[0].date()} ~ {common[-1].date()}')

# 显示各资产详情
print('\n=== 公用日期前后的数据详情 ===')
start_date = datetime(2014,10,17)
end_date = datetime(2026,6,12)
for key in sorted(weekly):
    d = weekly[key]
    print(f'{key:<10}: {len(d)}周 {d.iloc[0]["date"].date()}~{d.iloc[-1]["date"].date()}', end='')
    # 在公共区间的收益
    mask = (d['date'] >= start_date) & (d['date'] <= end_date)
    sub = d[mask]
    if len(sub) > 1:
        ret = (sub['close'].iloc[-1] / sub['close'].iloc[0] - 1) * 100
        yrs = len(sub) / 52
        cagr = (sub['close'].iloc[-1] / sub['close'].iloc[0]) ** (1/yrs) - 1
        print(f'  2014-2026: {ret:+.1f}% 年化{cagr*100:.1f}%')
    else:
        print(f'  2014-2026: 数据不足')
