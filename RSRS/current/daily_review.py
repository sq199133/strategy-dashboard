"""RSRS 每日复盘脚本 v2 — 2026-07-21"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = r'D:\QClaw_Trading\data\history'
POOL = {
    '510050':'上证50','510300':'沪深300','510500':'中证500',
    '512100':'中证1000','159915':'创业板','588000':'科创50',
    '513500':'标普500','513100':'纳斯达克','518880':'黄金','515080':'中证红利',
}

def load_etf(code):
    path = os.path.join(DATA_DIR, f'{code}.json')
    if not os.path.exists(path): return None
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        records = raw.get('records', raw.get('data', [raw]))
    else: records = raw
    df = pd.DataFrame(records)
    rename = {}
    for col in df.columns:
        cl = col.lower()
        if cl in ('day','date'): rename[col]='date'
        elif cl=='o': rename[col]='open'
        elif cl=='h': rename[col]='high'
        elif cl=='l': rename[col]='low'
        elif cl=='c': rename[col]='close'
        elif cl in ('vol','volume'): rename[col]='volume'
    if rename: df.rename(columns=rename, inplace=True)
    if 'date' not in df.columns or 'close' not in df.columns: return None
    cols = ['date','close']
    if all(c in df.columns for c in ['high','low']): cols.extend(['high','low'])
    df = df[cols]
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').reset_index(drop=True)

def calc_mom(df, w):
    if df is None or len(df) < w+2: return None
    df = df.copy(); df['ret'] = df['close'].pct_change()
    df['mom'] = (1+df['ret']).rolling(w).apply(lambda x: x.prod()-1, raw=False)
    return float(df['mom'].iloc[-1])

def calc_rsrs(df, n=18, m=1200):
    if df is None or len(df) < m+n or 'high' not in df.columns or 'low' not in df.columns:
        return None, None
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
    return float(df['zscore'].iloc[-1]), float(df['beta'].iloc[-1])

def calc_vol(df, target=0.16, window=70):
    if df is None or len(df) < 20: return None, None
    df = df.copy(); df['ret'] = df['close'].pct_change()
    w = min(window, len(df)-2)
    vol = df['ret'].rolling(w).std() * np.sqrt(252)
    lv = float(vol.iloc[-1])
    pos = min(0.9, max(0.1, target/lv)) if lv > 0 else 0.9
    return lv, pos

# ========== 数据概览 ==========
hs = load_etf('510300')
print("=" * 62)
print(f"RSRS 每日复盘 | {hs['date'].iloc[-1].strftime('%Y-%m-%d')} | 数据 {hs['date'].iloc[0].strftime('%Y-%m-%d')} ~ {hs['date'].iloc[-1].strftime('%Y-%m-%d')} ({len(hs)}天)")
print("=" * 62)

# 1. HS300
z, beta = calc_rsrs(hs)
close = hs['close'].iloc[-1]
chg = (close / hs['close'].iloc[-2] - 1) * 100
vol, pos = calc_vol(hs)
print(f"\n【沪深300 基准】")
print(f"  收盘: {close:.2f} ({chg:+.2f}%)")
if z is not None:
    sig = '做多模式 🟢' if z >= 0.7 else ('空仓模式 🔴' if z <= -1.0 else '灰色区域 🟡')
    print(f"  RSRS z-score: {z:.3f}  beta={beta:.4f}  ({sig})")
if vol:
    print(f"  70d年化波动: {vol*100:.1f}% | 目标仓位: {pos*100:.0f}%")

# 2. 持仓 KC50
print(f"\n【持仓】588000 科创50")
kc = load_etf('588000')
if kc is not None:
    kc_close = kc['close'].iloc[-1]
    kc_chg = (kc_close / kc['close'].iloc[-2] - 1) * 100
    buy = 2.01
    pnl = (kc_close - buy) / buy * 100
    expire = pd.to_datetime('2026-08-05')
    rem = (expire - pd.Timestamp.today()).days
    print(f"  收盘: {kc_close:.3f}  ({kc_chg:+.2f}%)")
    print(f"  买入: 2.010 (06-24) | 浮盈: {pnl:+.2f}%")
    print(f"  锁仓到期: 08-05 (剩 {rem} 天)")
    # KC50 RSRS (short window for individual ETF)
    z_kc, b_kc = calc_rsrs(kc, m=600)  # KC50 has 1377 records, 600 is safe
    if z_kc is not None:
        kc_sig = '做多 🟢' if z_kc >= 0.7 else ('空仓 🔴' if z_kc <= -1.0 else '灰色 🟡')
        print(f"  KC50 RSRS(M=600): {z_kc:.3f} ({kc_sig})")

# 3. C63 动量排名
print(f"\n【动量排名】")
ranks = []
for code, name in POOL.items():
    df = load_etf(code)
    c63 = calc_mom(df, 63); c21 = calc_mom(df, 21)
    last = df['date'].iloc[-1].strftime('%m-%d') if df is not None else 'N/A'
    ranks.append({'code':code,'name':name,'c63':c63,'c21':c21,'last':last})
ranks.sort(key=lambda x: x['c63'] if x['c63'] is not None else -999, reverse=True)
print(f"  {'#':<4} {'代码':<8} {'名称':<8} {'C63(63d)':<12} {'C21(21d)':<10} {'数据':<8}")
print(f"  {'-'*48}")
for i, r in enumerate(ranks, 1):
    c63 = f"{r['c63']*100:+.1f}%" if r['c63'] is not None else 'N/A'
    c21 = f"{r['c21']*100:+.1f}%" if r['c21'] is not None else 'N/A'
    mk = ' ← 持仓' if r['code'] == '588000' else ''
    print(f"  {i:<4} {r['code']:<8} {r['name']:<8} {c63:<12} {c21:<10} {r['last']:<8}{mk}")

# 4. C63 趋势
print(f"\n【C63 趋势】KC50:")
if kc is not None and len(kc) > 65:
    df = kc.copy(); df['ret'] = df['close'].pct_change()
    df['c63'] = (1+df['ret']).rolling(63).apply(lambda x: x.prod()-1, raw=False)
    for _, r in df.dropna(subset=['c63']).tail(10).iterrows():
        print(f"    {r['date'].strftime('%m-%d')}: C63={r['c63']*100:+.1f}%")

# 5. 操作建议
print(f"\n{'='*62}")
print("【操作建议】")
if z is not None and kc is not None:
    print(f"  🟢 大盘: RSRS z={z:.3f} ({sig}) | 波动目标仓位 {pos*100:.0f}%")
    print(f"  📊 KC50: 浮盈 {pnl:+.2f}% | C63排第1(+{ranks[0]['c63']*100:.1f}%)")
    if z >= 0.7:
        print(f"  ✅ 做多模式，KC50锁仓中继续持有")
    elif z <= -1.0:
        print(f"  🔴 空仓模式，但锁仓期内不动，到期清仓")
    else:
        print(f"  🟡 灰色区域，KC50持仓不动")
    print(f"  ⏰ 下个决策节点: 2026-08-05 (锁仓到期，剩 {rem} 天)")
print("=" * 62)
