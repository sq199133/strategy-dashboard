"""周五 2026-07-17 行情诊断"""
import sys, json, os, numpy as np, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = r'D:\QClaw_Trading\data\history'

# ETF池
POOL = {
    '510050': 'SH50', '510300': 'HS300', '510500': 'ZZ500',
    '512100': 'ZZ1000', '159915': 'CYB', '588000': 'KC50',
    '513500': 'SP500', '513100': 'NSDQ', '518880': 'GOLD',
    '162411': 'OIL', '515080': 'ZSHL',
}

def load_etf(code):
    path = os.path.join(DATA_DIR, code + '.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        records = raw.get('records', raw.get('data', []))
    else:
        records = raw
    import pandas as pd
    df = pd.DataFrame(records)
    col_map = {'date': 'date', 'day': 'date', 'close': 'close', 'c': 'close',
                'volume': 'volume', 'vol': 'volume'}
    for k, v in col_map.items():
        if k in df.columns and v not in df.columns:
            df.rename(columns={k: v}, inplace=True)
    if 'date' in df.columns and 'close' in df.columns:
        df = df[['date', 'close']].dropna()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
    return df

def compute_c63(df):
    if df is None or len(df) < 65:
        return None
    df = df.copy()
    df['ret'] = df['close'].pct_change()
    df['c63'] = (1 + df['ret']).rolling(63).apply(lambda x: x.prod() - 1, raw=False)
    return df['c63'].iloc[-1]

def compute_rsrs_zscore(df, n=18, m=1200):
    """Compute RSRS z-score from HS300 daily data"""
    if df is None or len(df) < m + 10:
        return None
    df = df.copy()
    df['ret'] = df['close'].pct_change()
    df['high_low'] = df['close']  # use close as proxy if no high/low
    # Simple RSRS: rolling correlation of close with lagged close
    df['rsrs'] = df['close'].rolling(n).apply(
        lambda x: np.corrcoef(x, np.arange(len(x)))[0,1] if len(x)>1 else 0, raw=False
    )
    df['rsrs_z'] = (df['rsrs'] - df['rsrs'].rolling(m).mean()) / df['rsrs'].rolling(m).std()
    return df['rsrs_z'].iloc[-1]

# Check data dirs
print("=== 数据目录检查 ===")
paths_to_check = [
    r'D:\QClaw_Trading\data\history',
    r'D:\QClaw_Trading\data\akshare_etf',
    r'D:\QClaw_Trading\scripts\data',
    r'D:\QClaw_Trading\RSRS\scripts',
]
for p in paths_to_check:
    exists = os.path.exists(p)
    files = []
    if exists:
        files = [f for f in os.listdir(p) if f.endswith('.json')][:3]
    print(f"  {p}: {'EXISTS' if exists else 'MISSING'} {files}")

# Try to find HS300 data
print("\n=== 尝试加载 ETF 数据 ===")
hs300 = load_etf('510300')
if hs300 is not None:
    print(f"HS300: {len(hs300)} rows, last date: {hs300['date'].iloc[-1]}")
else:
    # Look for any directory with ETF json files
    for root, dirs, files in os.walk(r'D:\QClaw_Trading'):
        for f in files:
            if f == '510300.json':
                print(f"Found: {os.path.join(root, f)}")
                break

# C63 rankings
print("\n=== C63 动量排名 ===")
rankings = []
for code, name in POOL.items():
    df = load_etf(code)
    c63 = compute_c63(df)
    last_date = df['date'].iloc[-1] if df is not None else 'N/A'
    rankings.append({'code': code, 'name': name, 'c63': c63, 'last_date': last_date})
    status = f"{c63*100:+.1f}%" if c63 is not None else "N/A"
    print(f"  {code} ({name}): C63={status} | data:{last_date}")

rankings.sort(key=lambda x: x['c63'] if x['c63'] is not None else -999, reverse=True)
print("\n=== 排名 Top5 ===")
for i, r in enumerate(rankings[:5], 1):
    print(f"  {i}. {r['code']} ({r['name']}): {r['c63']*100:+.1f}%")

# Position: KC50
kc50 = load_etf('588000')
if kc50 is not None:
    last = kc50.iloc[-1]
    buy_price = 2.01
    pnl = (last['close'] - buy_price) / buy_price * 100
    print(f"\n=== 持仓 KC50 ===")
    print(f"  最新价: {last['close']:.3f} ({last['date']})")
    print(f"  买入价: {buy_price:.3f}")
    print(f"  浮动盈亏: {pnl:+.2f}%")
