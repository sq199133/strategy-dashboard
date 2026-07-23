# -*- coding: utf-8 -*-
"""
RSRS + 宽基估值轮动 组合策略
=============================
三层架构（基于RSRS v4 + 估值轮动v1）：

  Layer 1: RSRS大盘择时（沪深300日线，N=18/M=900，buy=0.7/sell=-1.0）
  Layer 2: 估值轮动选股（宽基ETF池：沪深300/中证500/中证1000/创业板/科创50）
           - 估值分位：滚动60月 price/MA12乖离率百分位
           - 选最便宜的Top1或Top2
           - 对比动量选股（RSRS v4的C63）
  Layer 3: 波动率仓位管理（目标16%，VW=70d）

数据：本地ETF历史（2018-01 ~ 2026-07）
对比基准：RSRS v4（C63动量），纯估值轮动

结论输出：
  1. 纯RSRS+估值 vs RSRS+动量
  2. 宽基池内轮动 vs 全市场池轮动
  3. 当前（2026-07）估值信号
"""

import os, json, sys, warnings, argparse
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

# ────────────────────────────────
# 配置
# ────────────────────────────────
DATA_DIR = r'D:\QClaw_Trading\data\history'
OUT_DIR = r'D:\QClaw_Trading\RSRS'

# 宽基ETF池（5只）
WIDE_POOL = {
    '510300': '沪深300',
    '510500': '中证500',
    '512100': '中证1000',
    '159915': '创业板指',
    '588080': '科创50',
}

# 全市场池（RSRS v4池 + 宽基，重复用宽基名）
FULL_POOL = {
    '510300': '沪深300',   # 宽基
    '510050': 'SH50',      # 宽基
    '159902': '中盘',
    '159949': 'CYB50',
    '512100': '中证1000',
    '159928': '消费',
    '512800': '银行',
    '512400': '有色',
    '512200': '地产',
    '510160': '工业',
    '518880': '黄金',
    '159905': '红利',
    '510810': '上海国企',
    # 宽基补入（无重复已有）
    '510500': '中证500',
    '588080': '科创50',
}


# ────────────────────────────────
# 1. 数据加载
# ────────────────────────────────
def load_etf(code):
    path = os.path.join(DATA_DIR, code + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        records = raw.get('records', raw.get('data', []))
    else:
        records = raw
    df = pd.DataFrame(records)
    dc = next((c for c in df.columns if c.lower() in ['date', 'day']), None)
    cc = next((c for c in df.columns if c.lower() in ['close', 'c']), None)
    hc = next((c for c in df.columns if c.lower() in ['high', 'h']), None)
    lc = next((c for c in df.columns if c.lower() in ['low', 'l']), None)
    if not dc or not cc: raise ValueError(f'{code}: 无日期/收盘价字段 {list(df.columns)}')
    df['date'] = pd.to_datetime(df[dc])
    for col, mapper in [(cc, 'close'), (hc, 'high'), (lc, 'low')]:
        if col:
            df[mapper] = pd.to_numeric(df[col], errors='coerce')
    df = df[['date', 'close', 'high', 'low']].dropna()
    df = df.drop_duplicates('date', keep='last').sort_values('date').reset_index(drop=True)
    return df[df['close'] > 0]


def build_panel(codes, min_rows=300):
    """加载多只ETF并对齐"""
    frames = {}
    for code in codes:
        try:
            df = load_etf(code)
            if len(df) >= min_rows:
                frames[code] = df.set_index('date')
            else:
                print(f'  跳过 {code}: {len(df)}行 < {min_rows}')
        except Exception as e:
            print(f'  跳过 {code}: {e}')
    if not frames:
        raise ValueError('无有效数据')
    common = sorted(set.intersection(*[set(df.index) for df in frames.values()]))
    panel = pd.DataFrame({'date': common}).set_index('date')
    for code, df in frames.items():
        panel[code] = panel.index.map(df['close'])
    return frames, panel


# ────────────────────────────────
# 2. RSRS计算
# ────────────────────────────────
def compute_rsrs(df, n=18, m=900, buy_thr=0.7, sell_thr=-1.0):
    high, low = df['high'].values, df['low'].values
    beta = np.full(len(df), np.nan)
    for i in range(n - 1, len(df)):
        y, x = high[i-n+1:i+1], low[i-n+1:i+1]
        if not (np.isnan(x).any() or np.isnan(y).any()):
            xm = np.column_stack([np.ones(n), x])
            try: beta[i] = np.linalg.lstsq(xm, y, rcond=None)[0][1]
            except: pass
    zscore = np.full(len(beta), np.nan)
    for i in range(m - 1, len(beta)):
        v = beta[i-m+1:i+1]; vv = v[~np.isnan(v)]
        if len(vv) >= 100:
            mu, sg = np.mean(vv), np.std(vv, ddof=1)
            if sg > 0: zscore[i] = (beta[i] - mu) / sg
    signal = np.zeros(len(zscore)); pos = 0
    for i in range(len(zscore)):
        if not np.isnan(zscore[i]):
            if zscore[i] > buy_thr: pos = 1
            elif zscore[i] < sell_thr: pos = 0
        signal[i] = pos
    return signal, zscore


# ────────────────────────────────
# 3. 估值分位计算（滚动60月）
# ────────────────────────────────
def compute_val_score(daily_df, pct_window=60, min_pct=36):
    """
    计算每日估值分位
    估值代理：price / MA12（乖离率）
    val_score = 1 - pct(price_to_ma)  越高=越便宜
    """
    close = daily_df['close'].values
    dates = daily_df.index.values
    
    # MA12（12日均线，日频）
    ma12 = pd.Series(close).rolling(12, min_periods=6).mean().values
    ptm = close / (ma12 + 1e-10)
    
    # 估值分位（滚动窗口，按日对齐）
    pct = np.full(len(close), np.nan)
    for i in range(pct_window, len(close)):
        window = ptm[max(0, i-pct_window):i]
        valid = window[~np.isnan(window)]
        if len(valid) >= min_pct:
            pct[i] = (valid > ptm[i]).sum() / len(valid)
    
    return pd.Series(pct, index=dates, name='val_score')


def compute_val_score_weekly(daily_df, pct_window=60, min_pct=36):
    """
    计算每周估值分位（月末对齐）
    """
    m = daily_df.copy()
    m['month'] = m.index.to_period('M')
    monthly = m.groupby('month').agg(
        close=('close', 'last'),
    ).reset_index()
    monthly['date'] = monthly['month'].dt.to_timestamp()
    
    close = monthly['close'].values
    dates = monthly['date'].values
    ma12 = pd.Series(close).rolling(12, min_periods=6).mean().values
    ptm = close / (ma12 + 1e-10)
    
    pct = np.full(len(close), np.nan)
    for i in range(pct_window, len(close)):
        window = ptm[max(0, i-pct_window):i]
        valid = window[~np.isnan(window)]
        if len(valid) >= min_pct:
            pct[i] = (valid > ptm[i]).sum() / len(valid)
    
    return pd.Series(pct, index=dates, name='val_score')


# ────────────────────────────────
# 4. 动量计算（C63）
# ────────────────────────────────
def compute_c63(daily_df, date):
    """计算某日的C63复合动量"""
    row = daily_df.xs(date) if date in daily_df.index else None
    if row is None: return None
    rets = []
    for lb in (50, 63, 75):
        idx = daily_df.index.get_loc(date)
        if idx >= lb:
            p_start = daily_df.iloc[idx - lb]['close']
            p_end = daily_df.iloc[idx]['close']
            if p_start > 0:
                rets.append(p_end / p_start - 1)
    return np.mean(rets) if rets else None


# ────────────────────────────────
# 5. 波动率仓位
# ────────────────────────────────
def compute_vol_scaling(df, dates, vw=70, tv=0.16):
    dfi = df.set_index('date')['close']
    ret = dfi.pct_change().fillna(0)
    ann_vol = ret.rolling(vw).std() * np.sqrt(252)
    scale = (tv / ann_vol).clip(0.1, 0.9).fillna(1.0)
    return scale[scale.index.isin(dates)]


# ────────────────────────────────
# 6. 回测引擎
# ────────────────────────────────
def backtest(name, data, panel, rsrs_signal, rsrs_dates,
             val_scores,       # {code: Series(date->val_score)}
             selector,          # fn(panel_date) -> [(code, score)]
             top_n, rebal_days, vol_scaling, oos_start=None):
    """
    selector(panel_date, val_scores) -> list of (code, score) sorted desc
    """
    n = len(panel)
    positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    
    # 对齐RSRS信号
    rsrs_ns = rsrs_dates.astype('datetime64[ns]')
    panel_ns = panel.index.values.astype('datetime64[ns]')
    sig_idx = np.searchsorted(rsrs_ns, panel_ns)
    sig_map = pd.Series(
        [rsrs_signal[i] if i < len(rsrs_signal) else 0 for i in sig_idx],
        index=panel.index
    )
    
    # 对齐估值分位
    val_map = {}
    for code, vs in val_scores.items():
        vs_ns = vs.index.values.astype('datetime64[ns]')
        panel_ns2 = panel.index.values.astype('datetime64[ns]')
        idx2 = np.searchsorted(vs_ns, panel_ns2)
        val_map[code] = pd.Series(
            [vs.iloc[min(i, len(vs)-1)] if i < len(vs) else np.nan for i in idx2],
            index=panel.index
        )
    
    oos_start = pd.Timestamp(oos_start) if oos_start else None
    nr = None
    holdings = []
    
    for i, date in enumerate(panel.index):
        market = int(sig_map.loc[date])
        scale = float(vol_scaling.loc[date]) if date in vol_scaling.index else 1.0
        
        if not market or scale <= 0:
            holdings = []; nr = None
            positions.loc[date] = 0.0
            continue
        
        if nr is None or date >= nr:
            candidates = selector(date, val_map, data)
            candidates = [(c, s) for c, s in candidates if c in panel.columns
                          and not np.isnan(val_map.get(c, pd.Series({date: np.nan})).get(date, np.nan))]
            candidates.sort(key=lambda x: -x[1])
            holdings = [c for c, _ in candidates[:top_n]]
            if holdings:
                nr = panel.index[min(i + rebal_days, n - 1)]
            else:
                nr = None
        
        if holdings:
            w = scale / len(holdings)
            for code in holdings:
                positions.loc[date, code] = w
    
    # 绩效分析
    daily_ret = panel.pct_change().fillna(0)
    strat_ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)
    bh_ret = daily_ret['510300'] if '510300' in panel.columns else daily_ret.mean(axis=1)
    
    if oos_start:
        mask = strat_ret.index >= oos_start
        strat_ret = strat_ret[mask]
        bh_ret = bh_ret[mask]
        positions = positions[positions.index >= oos_start]
    
    cum = (1 + strat_ret).cumprod()
    ann = cum.iloc[-1] ** (252.0 / len(cum)) - 1
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    sd = strat_ret.std()
    sharpe = np.sqrt(252) * strat_ret.mean() / sd if sd > 1e-10 else 0
    win = (strat_ret > 0).mean()
    
    # 年度
    annual = {}
    for yr in sorted(set(strat_ret.index.year)):
        m = strat_ret.index.year == yr
        nd = m.sum()
        if nd < 20: continue
        yr_ret = strat_ret[m]
        cy = (1 + yr_ret).cumprod().iloc[-1] ** (252 / nd) - 1
        bh_y = (1 + bh_ret[m]).cumprod().iloc[-1] ** (252 / nd) - 1
        annual[yr] = {'ret': cy, 'bh': bh_y, 'xs': cy - bh_y}
    
    # 持仓统计
    pos_days = (positions.sum(axis=1) > 0).sum()
    total_days = len(positions)
    
    return {
        'name': name,
        'ann': ann, 'mdd': mdd, 'sharpe': sharpe, 'win': win,
        'pos_pct': pos_days / total_days,
        'n_days': len(strat_ret),
        'annual': annual,
        'strat_ret': strat_ret,
    }


# ────────────────────────────────
# 7. 选股函数工厂
# ────────────────────────────────
def sel_val_top1(date, val_map):
    """估值Top1"""
    scores = []
    for code, series in val_map.items():
        v = series.get(date, np.nan)
        if not np.isnan(v):
            scores.append((code, v))
    scores.sort(key=lambda x: -x[1])
    return scores[:1] if scores else []

def sel_val_top2(date, val_map):
    scores = []
    for code, series in val_map.items():
        v = series.get(date, np.nan)
        if not np.isnan(v):
            scores.append((code, v))
    scores.sort(key=lambda x: -x[1])
    return scores[:2] if scores else []

def sel_val_low_thr(date, val_map, thr=0.6, top_n=1):
    """低估过滤：val > thr"""
    scores = [(c, s.get(date, np.nan)) for c, s in val_map.items()]
    scores = [(c, v) for c, v in scores if not np.isnan(v) and v > thr]
    scores.sort(key=lambda x: -x[1])
    if not scores:
        return sel_val_top1(date, val_map)  # fallback
    return scores[:top_n]

def sel_c63_top1(date, data):
    """C63动量Top1"""
    scores = []
    for code, df in data.items():
        if date in df.index:
            s = compute_c63(df, date)
            if s is not None and s > 0:
                scores.append((code, s))
    scores.sort(key=lambda x: -x[1])
    return scores[:1] if scores else []

def sel_val_mom(date, val_map, data):
    """估值+动量综合 score = val * (1 + max(mom, 0))"""
    # val: higher=better, mom: use last 63d return
    scores = []
    for code in val_map:
        v = val_map[code].get(date, np.nan)
        if np.isnan(v): continue
        df = data.get(code)
        if df is None or date not in df.index: continue
        idx = df.index.get_loc(date)
        if idx >= 63:
            mom = df.iloc[idx]['close'] / df.iloc[idx-63]['close'] - 1
        else:
            mom = 0
        s = v * (1 + max(mom, 0))
        scores.append((code, s))
    scores.sort(key=lambda x: -x[1])
    return scores[:1] if scores else []

def sel_val_low_top1_mom_confirm(date, val_map, data, extra_data=None):
    """低估(val>0.6) + 动量正"""
    candidates = [(c, v.get(date, np.nan)) for c, v in val_map.items()]
    candidates = [(c, v) for c, v in candidates if not np.isnan(v) and v > 0.6]
    # 过滤动量
    filtered = []
    for code, v in candidates:
        df = data.get(code)
        if df is None or date not in df.index: continue
        idx = df.index.get_loc(date)
        if idx >= 63:
            mom = df.iloc[idx]['close'] / df.iloc[idx-63]['close'] - 1
            if mom > 0:
                filtered.append((code, v))
    if not filtered:
        filtered = candidates[:1] if candidates else []
    filtered.sort(key=lambda x: -x[1])
    return filtered[:1]


# ────────────────────────────────
# 8. 主流程
# ────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pool', default='wide', choices=['wide', 'full'])
    parser.add_argument('--rb', type=int, default=42)
    parser.add_argument('--top', type=int, default=1)
    parser.add_argument('--oos', default='2022-07-01')
    args = parser.parse_args()
    
    pool = WIDE_POOL if args.pool == 'wide' else FULL_POOL
    
    print('=' * 65)
    print(f'  RSRS + 宽基估值轮动 组合策略')
    print(f'  池: {"宽基" if args.pool=="wide" else "全市场"} | Top{args.top} | 调仓{args.rb}d | OOS从{args.oos}')
    print('=' * 65)
    
    # 加载数据
    print(f'\n加载数据: {len(pool)}只ETF')
    data, panel = build_panel(pool, min_rows=300)
    common_codes = list(panel.columns)
    print(f'面板: {panel.index[0].date()} ~ {panel.index[-1].date()}, {len(panel)}日')
    
    # RSRS
    print('\n计算RSRS...')
    df300 = load_etf('510300')
    rsrs_signal, rsrs_z = compute_rsrs(df300, n=18, m=900, buy_thr=0.7, sell_thr=-1.0)
    rsrs_dates = df300['date'].values
    
    # 估值分位（日频）
    print('计算估值分位（日频）...')
    val_scores = {}
    for code in common_codes:
        df = data.get(code)
        if df is not None:
            vs = compute_val_score(df, pct_window=252, min_pct=126)
            val_scores[code] = vs
            print(f'  {pool.get(code, code)}: {vs.dropna().index[0].date() if not vs.dropna().empty else "N/A"} ~ {vs.dropna().index[-1].date() if not vs.dropna().empty else "N/A"} ({vs.dropna().shape[0]}日)')
    
    # 波动率
    vol_scaling = compute_vol_scaling(df300, panel.index)
    
    # 对齐到panel
    vs_panel = {}
    for code, vs in val_scores.items():
        vs2 = vs.reindex(panel.index).ffill().fillna(0.5)
        vs_panel[code] = vs2
    
    # ────────────────────────────
    # 运行各策略
    # ────────────────────────────
    oos_start = args.oos
    
    strategies = [
        ('A_RSRS+估值Top1',      lambda d, vm, _d: sel_val_top1(d, vm), 1),
        ('B_RSRS+估值Top2',      lambda d, vm, _d: sel_val_top2(d, vm), 2),
        ('C_RSRS+低估过滤Top1',  lambda d, vm, _d: sel_val_low_thr(d, vm, 0.6, 1), 1),
        ('D_RSRS+C63动量Top1',   lambda d, vm, dd: sel_c63_top1(d, dd), 1),
        ('E_RSRS+估值动量综合',   lambda d, vm, dd: sel_val_mom(d, vm, dd), 1),
        ('F_RSRS+低估动量确认',  lambda d, vm, dd: sel_val_low_top1_mom_confirm(d, vm, dd), 1),
    ]
    
    print(f'\n运行 {len(strategies)} 个策略...')
    results = []
    for name, sel_fn, top_n in strategies:
        print(f'  {name}...', end='', flush=True)
        r = backtest(name, data, panel, rsrs_signal, rsrs_dates,
                    val_scores, sel_fn, top_n, args.rb, vol_scaling, oos_start)
        results.append(r)
        oos_yr_key = int(oos_start[:4])
        oos_ret = r['annual'].get(oos_yr_key, {}).get('ret', 0) if r['annual'] else 0
        print(f' Full{len(panel)}d ann={r["ann"]*100:.1f}% Sharpe={r["sharpe"]:.2f} | OOS={oos_ret*100:+.1f}%')
    
    # 对比: 纯估值轮动（无RSRS）
    print('  纯估值轮动(无RSRS)...', end='', flush=True)
    
    def backtest_no_rsrs(name, data, panel, val_scores, sel_fn, top_n, rebal_days, vol_scaling):
        n = len(panel)
        positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
        val_map = {}
        for code, vs in val_scores.items():
            vs2 = vs.reindex(panel.index).ffill().fillna(0.5)
            val_map[code] = vs2
        vol_s = vol_scaling.reindex(panel.index).fillna(1.0)
        
        nr = None; holdings = []
        for i, date in enumerate(panel.index):
            scale = float(vol_s.loc[date]) if date in vol_s.index else 1.0
            if nr is None or date >= nr:
                candidates = sel_fn(date, val_map, data)
                candidates = [(c, s) for c, s in candidates if c in panel.columns]
                candidates.sort(key=lambda x: -x[1])
                holdings = [c for c, _ in candidates[:top_n]]
                if holdings:
                    nr = panel.index[min(i + rebal_days, n - 1)]
                else:
                    nr = None
            if holdings:
                w = scale / len(holdings)
                for code in holdings:
                    positions.loc[date, code] = w
        
        daily_ret = panel.pct_change().fillna(0)
        strat_ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)
        cum = (1 + strat_ret).cumprod()
        ann = cum.iloc[-1] ** (252.0 / len(cum)) - 1
        peak = cum.cummax(); mdd = ((cum - peak) / peak).min()
        sd = strat_ret.std()
        sharpe = np.sqrt(252) * strat_ret.mean() / sd if sd > 1e-10 else 0
        annual = {}
        for yr in sorted(set(strat_ret.index.year)):
            m = strat_ret.index.year == yr
            nd = m.sum()
            if nd < 20: continue
            yr_ret = strat_ret[m]
            cy = (1 + yr_ret).cumprod().iloc[-1] ** (252 / nd) - 1
            bh_y = (1 + daily_ret['510300'][m]).cumprod().iloc[-1] ** (252 / nd) - 1 if '510300' in panel.columns else 0
            annual[yr] = {'ret': cy, 'bh': bh_y, 'xs': cy - bh_y}
        pos_days = (positions.sum(axis=1) > 0).sum()
        return {'name': name, 'ann': ann, 'mdd': mdd, 'sharpe': sharpe,
                'win': (strat_ret > 0).mean(), 'pos_pct': pos_days/len(positions),
                'n_days': len(strat_ret), 'annual': annual, 'strat_ret': strat_ret}
    
    r_no_rsrs = backtest_no_rsrs('G_纯估值Top1(无RSRS)', data, panel, val_scores,
                                   lambda d, vm, _dd: sel_val_top1(d, vm), 1, args.rb, vol_scaling)
    results.append(r_no_rsrs)
    print(f' Full{len(panel)}d ann={r_no_rsrs["ann"]*100:.1f}% Sharpe={r_no_rsrs["sharpe"]:.2f}')
    
    # ────────────────────────────
    # 打印结果
    # ────────────────────────────
    print('\n' + '=' * 75)
    print(f'  RSRS + 宽基估值轮动 策略对比 (池: {"宽基" if args.pool=="wide" else "全市场"}, OOS从{oos_start})')
    print('=' * 75)
    print(f"{'策略':<25}{'全样年化':>9}{'全样Sharpe':>10}{'全样MDD':>9}{'胜率':>7}{'持仓%':>7}")
    print('-' * 75)
    for r in sorted(results, key=lambda x: -x['sharpe']):
        print(f"{r['name']:<25}{r['ann']*100:>8.1f}%{r['sharpe']:>9.2f}{r['mdd']*100:>8.1f}%{r['win']*100:>6.1f}%{r['pos_pct']*100:>6.1f}%")
    
    # 年度对比
    print('\n--- 年度收益明细 ---')
    oos_yrs = [int(oos_start[:4]), int(oos_start[:4])+1, int(oos_start[:4])+2,
               int(oos_start[:4])+3, int(oos_start[:4])+4]
    print(f"{'策略':<25}", end='')
    for yr in oos_yrs:
        print(f'{yr:>8}', end='')
    print()
    for r in sorted(results, key=lambda x: -x['sharpe']):
        print(f"{r['name']:<25}", end='')
        for yr in oos_yrs:
            val = r['annual'].get(yr, {})
            ret = val.get('ret', 0) if val else 0
            print(f'{ret*100:>+7.1f}%', end='')
        print()
    
    # 与RSRS v4对比
    print('\n--- 对比RSRS v4历史记录 ---')
    print('  RSRS v4(13只ETF全样本):  年化21.5%  Sharpe 1.23  MDD -26.8%')
    print('  RSRS v4(OOS 2022-2025): 年化22.1%  Sharpe 1.31  MDD -18.7%')
    
    # 保存结果
    res_summary = []
    for r in results:
        annual_df = pd.DataFrame.from_dict(r['annual'], orient='index')
        res_summary.append({
            'name': r['name'], 'ann': r['ann'], 'mdd': r['mdd'],
            'sharpe': r['sharpe'], 'win': r['win'], 'pos_pct': r['pos_pct'],
        })
    pd.DataFrame(res_summary).to_csv(
        os.path.join(OUT_DIR, f'rsrs_val_combined_{args.pool}.csv'), index=False)
    print(f'\n结果已保存: rsrs_val_combined_{args.pool}.csv')
    
    print('=' * 65)

if __name__ == '__main__':
    main()
