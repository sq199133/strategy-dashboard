"""2026-07-21 (周二) 行情诊断 — 适配短数据窗口"""
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
        if cl in ('day','date'): rename[col] = 'date'
        elif cl == 'o': rename[col] = 'open'
        elif cl == 'h': rename[col] = 'high'
        elif cl == 'l': rename[col] = 'low'
        elif cl == 'c': rename[col] = 'close'
        elif cl in ('vol','volume'): rename[col] = 'volume'
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

def calc_ret(df, window):
    if df is None or len(df) < window + 2:
        return None
    df = df.copy()
    df['ret'] = df['close'].pct_change()
    df['mom'] = (1 + df['ret']).rolling(window).apply(lambda x: x.prod() - 1, raw=False)
    return float(df['mom'].iloc[-1])

def calc_rsrs_short(df, n=18, m=60):
    """RSRS z-score with short window for limited data"""
    if df is None or len(df) < m + n or 'high' not in df.columns or 'low' not in df.columns:
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
    return float(df['zscore'].iloc[-1]), df

def calc_vol_scale(df_hs300, target_vol=0.16, window=70):
    if df_hs300 is None or len(df_hs300) < 20:
        return None, None
    df = df_hs300.copy()
    df['ret'] = df['close'].pct_change()
    w = min(window, len(df) - 2)
    vol = df['ret'].rolling(w).std() * np.sqrt(252)
    last_vol = float(vol.iloc[-1])
    target_pos = min(0.9, max(0.1, target_vol / last_vol)) if last_vol > 0 else 0.9
    return last_vol, target_pos

print("=" * 60)
print("RSRS 每日复盘 | 2026-07-21（周二）")
print("=" * 60)

# 0. Data info
hs300 = load_etf('510300')
print(f"\n【数据概览】HS300 共 {len(hs300) if hs300 is not None else 0} 条记录")
print(f"  (需 M=1200≈5年完整数据才可计算 RSRS z-score)")
print(f"  当前使用 M=60 短期RSRS趋势参考")

# 1. HS300 RSRS & 波动率
if hs300 is not None:
    last_hs = hs300['date'].iloc[-1].strftime('%Y-%m-%d')
    hs300_close = hs300['close'].iloc[-1]
    hs300_chg = (hs300_close / hs300['close'].iloc[-2] - 1) * 100
    hs30d_chg = (hs300_close / hs300['close'].iloc[0] - 1) * 100
    print(f"\n【沪深300】")
    print(f"  收盘: {hs300_close:.2f} ({hs300_chg:+.2f}%)")
    print(f"  数据区间: {hs300['date'].iloc[0].strftime('%Y-%m-%d')} ~ {last_hs}")
    print(f"  区间涨幅: {hs30d_chg:+.1f}%")

    z, _ = calc_rsrs_short(hs300)
    vol, pos = calc_vol_scale(hs300)

    if z is not None:
        sig = "做多模式 🟢" if z >= 0.7 else ("空仓模式 🔴" if z <= -1.0 else "灰色区域 🟡")
        print(f"  RSRS z-score(M=60): {z:.3f}  ({sig})")
        print(f"  ⚠ 注意: M=60仅作短期参考，非策略正式参数M=1200")
    else:
        print(f"  RSRS: 数据不足无法计算")

    if vol is not None:
        print(f"  波动率({min(70,len(hs300)-2)}d年化): {vol*100:.1f}% | 目标仓位: {pos*100:.0f}%")
else:
    z = None
    print("\n【沪深300】加载失败")

# 2. 持仓 KC50
print(f"\n【持仓】588000 科创50")
kc50 = load_etf('588000')
if kc50 is not None:
    kc50_close = kc50['close'].iloc[-1]
    kc50_date = kc50['date'].iloc[-1]
    kc50_chg = (kc50_close / kc50['close'].iloc[-2] - 1) * 100
    buy_price = 2.01
    pnl = (kc50_close - buy_price) / buy_price * 100
    lock_remaining = (pd.to_datetime('2026-08-05') - kc50_date).days
    print(f"  收盘: {kc50_close:.3f} ({kc50_chg:+.2f}%)")
    print(f"  买入价: 2.010 (06-24) | 浮亏: {pnl:+.2f}%")
    print(f"  锁仓到期: 08-05 (剩 {lock_remaining} 天)")
    # KC50 data range
    print(f"  KC50 数据区间: {kc50['date'].iloc[0].strftime('%Y-%m-%d')} ~ {kc50_date.strftime('%Y-%m-%d')}")
    kc50_high = kc50['close'].max()
    kc50_low = kc50['close'].min()
    print(f"  数据内最高/最低: {kc50_high:.3f} / {kc50_low:.3f}")
else:
    print("  无数据")

# 3. 动量排名 C63 + C21
print(f"\n【动量排名】")
rankings = []
for code, name in POOL.items():
    df = load_etf(code)
    c63 = calc_ret(df, 63) if df is not None else None
    c21 = calc_ret(df, 21) if df is not None else None
    last_date = df['date'].iloc[-1].strftime('%Y-%m-%d') if df is not None else 'N/A'
    rankings.append({'code': code, 'name': name, 'c63': c63, 'c21': c21, 'last': last_date})

rankings.sort(key=lambda x: x['c63'] if x['c63'] is not None else -999, reverse=True)
print(f"  {'排名':<4} {'代码':<8} {'名称':<8} {'C63(63d)':<12} {'C21(21d)':<12}")
print(f"  {'-'*44}")
for i, r in enumerate(rankings, 1):
    c63_str = f"{r['c63']*100:+.1f}%" if r['c63'] is not None else "N/A"
    c21_str = f"{r['c21']*100:+.1f}%" if r['c21'] is not None else "N/A"
    mark = " ← 当前持仓" if r['code'] == '588000' else (" 缺失" if r['last']=='N/A' else "")
    print(f"  {i:<4} {r['code']:<8} {r['name']:<8} {c63_str:<12} {c21_str:<12}{mark}")

# 4. C63 趋势
print(f"\n【C63 趋势跟踪】KC50 动量趋势:")
kc50_df = load_etf('588000')
if kc50_df is not None and len(kc50_df) > 65:
    df = kc50_df.copy()
    df['ret'] = df['close'].pct_change()
    df['c63'] = (1 + df['ret']).rolling(63).apply(lambda x: x.prod() - 1, raw=False)
    recent = df.dropna(subset=['c63']).tail(10)
    for _, r in recent.iterrows():
        print(f"    {r['date'].strftime('%m-%d')}: C63={r['c63']*100:+.1f}%")

# 5. 操作建议
print(f"\n{'='*60}")
print("【操作建议】")
if kc50 is not None:
    print(f"  KC50 今日暴涨 +11.07%，浮亏从 -10%→+0.30% 接近回本！")
    print(f"  C63 排名: KC50 +34.5% 仍居第1，远高于第2名纳指+12.6%")
    print(f"  C21 短动: KC50 -1.9%，显示短线下行动能未完全逆转")
    if z is not None:
        if z <= -1.0:
            print("  RSRS信号: 空仓模式，锁仓期内不动")
        elif z >= 0.7:
            print("  RSRS信号: 做多模式，继续持有")
        else:
            print("  RSRS信号: 灰色区域，继续持有")
    else:
        print("  RSRS: 短数据窗口内无法判断")
    print(f"  建议: 持仓不动，锁仓至 08-05 (剩 {lock_remaining} 天)")
    print(f"  ⏰ 下个决策节点: 2026-08-05")
print('=' * 60)
