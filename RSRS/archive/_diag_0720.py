"""2026-07-20 (周一) 行情诊断"""
import sys, json, os, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = r'D:\QClaw_Trading\data\history'
POOL = {
    '510050': '上证50', '510300': '沪深300', '510500': '中证500',
    '512100': '中证1000', '159915': '创业板', '588000': '科创50',
    '513500': '标普500', '513100': '纳斯达克', '518880': '黄金',
    '162411': '原油', '515080': '中证红利',
}

def load_etf(code):
    path = os.path.join(DATA_DIR, code + '.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        records = raw.get('records', raw.get('data', [raw]))
    else:
        records = raw
    df = pd.DataFrame(records)
    rename = {}
    for col in df.columns:
        cl = col.lower()
        if cl == 'day': rename[col] = 'date'
        elif cl == 'o': rename[col] = 'open'
        elif cl == 'h': rename[col] = 'high'
        elif cl == 'l': rename[col] = 'low'
        elif cl == 'c': rename[col] = 'close'
        elif cl == 'vol': rename[col] = 'volume'
    if rename:
        df.rename(columns=rename, inplace=True)
    if 'date' not in df.columns or 'close' not in df.columns:
        return None
    cols = ['date', 'close']
    if all(c in df.columns for c in ['high','low']):
        cols.extend(['high','low'])
    df = df[cols]
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

def calc_c63(df):
    if df is None or len(df) < 65:
        return None
    df = df.copy()
    df['ret'] = df['close'].pct_change()
    df['c63'] = (1 + df['ret']).rolling(63).apply(lambda x: x.prod() - 1, raw=False)
    return float(df['c63'].iloc[-1])

def calc_rsrs(df, n=18, m=1200):
    if df is None or len(df) < m + n:
        return None
    df = df.copy()
    betas = []
    for i in range(n-1, len(df)):
        x = df['low'].iloc[i-n+1:i+1].values
        y = df['high'].iloc[i-n+1:i+1].values
        b, _ = np.polyfit(x, y, 1)
        betas.append(b)
    df = df.iloc[n-1:].copy()
    df['beta'] = betas
    df['zscore'] = (df['beta'] - df['beta'].rolling(m).mean()) / df['beta'].rolling(m).std()
    return float(df['zscore'].iloc[-1])

def calc_vol_scale(df_hs300, target_vol=0.16, window=70):
    if df_hs300 is None or len(df_hs300) < window + 5:
        return None, None
    df = df_hs300.copy()
    df['ret'] = df['close'].pct_change()
    vol = df['ret'].rolling(window).std() * np.sqrt(252)
    last_vol = float(vol.iloc[-1])
    target_pos = min(0.9, max(0.1, target_vol / last_vol)) if last_vol > 0 else 0.9
    return last_vol, target_pos

print("=" * 60)
print("RSRS 每日复盘 | 2026-07-20（周一）")
print("=" * 60)

# 1. HS300 RSRS
hs300 = load_etf('510300')
if hs300 is not None:
    last_hs = hs300['date'].iloc[-1]
    hs300_close = hs300['close'].iloc[-1]
    print(f"\n【沪深300】数据至: {last_hs} | 最新收盘: {hs300_close:.2f}")

    if 'high' in hs300.columns and 'low' in hs300.columns:
        z = calc_rsrs(hs300)
        vol, pos = calc_vol_scale(hs300)
    else:
        hs300['high'] = hs300['close'] * 1.005
        hs300['low'] = hs300['close'] * 0.995
        z = calc_rsrs(hs300)
        vol, pos = calc_vol_scale(hs300)

    if z is not None:
        sig = "做多模式 🟢" if z >= 0.7 else ("空仓模式 🔴" if z <= -1.0 else "灰色区域 🟡")
        print(f"  RSRS z-score: {z:.3f}  ({sig})")
    if vol is not None:
        print(f"  70d年化波动: {vol*100:.1f}% | 目标仓位: {pos*100:.0f}%")
else:
    z = None
    print(f"\n【沪深300】数据加载失败")

# 2. 持仓 KC50
print(f"\n【持仓】588000 科创50")
kc50 = load_etf('588000')
if kc50 is not None:
    kc50_close = kc50['close'].iloc[-1]
    kc50_date = kc50['date'].iloc[-1].strftime('%Y-%m-%d')
    buy_price = 2.01
    buy_date = '2026-06-24'
    lock_expire = '2026-08-05'
    pnl = (kc50_close - buy_price) / buy_price * 100
    lock_remaining = (pd.to_datetime(lock_expire) - pd.to_datetime(kc50_date)).days
    print(f"  收盘: {kc50_close:.3f} ({kc50_date})")
    print(f"  买入: {buy_price:.3f} ({buy_date})")
    print(f"  浮动盈亏: {pnl:+.2f}%")
    print(f"  锁仓到期: {lock_expire} (剩 {lock_remaining} 天)")
else:
    print("  无数据")

# 3. C63 排名
print(f"\n【C63 动量排名】")
rankings = []
for code, name in POOL.items():
    df = load_etf(code)
    c63 = calc_c63(df)
    last_date = df['date'].iloc[-1].strftime('%Y-%m-%d') if df is not None else 'N/A'
    rankings.append({'code': code, 'name': name, 'c63': c63, 'last': last_date})

rankings.sort(key=lambda x: x['c63'] if x['c63'] is not None else -999, reverse=True)
for i, r in enumerate(rankings, 1):
    c63_str = f"{r['c63']*100:+.1f}%" if r['c63'] is not None else "N/A"
    mark = " ← 当前持仓" if r['code'] == '588000' else ""
    print(f"  {i}. {r['code']} ({r['name']:　<4}) C63={c63_str} [数据: {r['last']}]{mark}")

# 4. 数据滞后提示
print(f"\n【数据检查】")
stale = []
for code, name in POOL.items():
    df = load_etf(code)
    if df is not None:
        last = df['date'].iloc[-1].strftime('%Y-%m-%d')
        if last < '2026-07-17':
            stale.append((code, name, last))
            print(f"  ⚠ {code} ({name}): 数据仅到 {last}")
        else:
            pass  # up to date
if not stale:
    print("  ✓ 所有ETF数据已更新至 07-17 或更晚")

# 5. 操作建议
print(f"\n{'='*60}")
print("【操作建议】")
if z is not None and kc50 is not None:
    if z <= -1.0:
        print("  信号: 🔴 空仓模式 (z ≤ -1.0)")
        print("  建议: KC50锁仓中，到期后清仓")
    elif z >= 0.7:
        print("  信号: 🟢 做多模式 (z ≥ 0.7)")
        print("  建议: KC50锁仓中，到期后按C63排名轮动")
    else:
        print("  信号: 🟡 灰色区域")
        print(f"  建议: KC50持仓不动，锁仓剩 {lock_remaining} 天")
    print(f"  持仓浮亏: {pnl:+.2f}%")
if stale:
    print(f"  ⚠ 提示: {len(stale)}只ETF数据滞后")
print(f"  ⏰ 下个决策节点: 2026-08-05 (锁仓到期)")
print('=' * 60)
