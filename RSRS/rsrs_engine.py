# -*- coding: utf-8 -*-
"""
RSRS策略引擎 — 可复用入口
========================
供周线动能(agent-10d)、RSRS择时专家(agent-11a)、4D框架(agent-da9f) 统一调用。

数据源统一：D:\QClaw_Trading\data\history\*.json

用法：
  from RSRS.rsrs_engine import RSRSStrategy, load_etf, etf_pool
  strat = RSRSStrategy()
  result = strat.run()
  print(result['rsrs']['zscore'])
"""

import json, os, sys, warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# ─── 路径 ───
DATA_DIR = r'D:\QClaw_Trading\data\history'
HISTORY_LONG = r'D:\QClaw_Trading\data\history_long_v2'

# ─── 默认ETF池（13只，RSRS v4终版） ───
ETF_POOL = {
    '510300': 'HS300',
    '510050': 'SH50',
    '159902': 'ZZSM100',
    '159949': 'CYB50',
    '512100': 'ZZ1000',
    '159928': 'CONSUM',
    '512800': 'BANK',
    '512400': 'METAL',
    '512200': 'REALEST',
    '510160': 'INDUP',
    '518880': 'GOLD',
    '159905': 'DIV',
    '510810': 'SHGQ',
}

# ─── 宽基ETF（5只，估值轮动池） ───
WIDE_POOL = {
    '510300': '沪深300',
    '510500': '中证500',
    '512100': '中证1000',
    '159915': '创业板指',
    '588080': '科创50',
    '510050': '上证50',
}


# ════════════════════════════════════════
# 1. 数据加载
# ════════════════════════════════════════

def load_etf(code):
    """
    加载单只ETF日线，兼容两种格式
    返回: DataFrame[date, open, high, low, close, volume]
    """
    path = os.path.join(DATA_DIR, code + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        records = raw.get('records', raw.get('data', [raw]))
        name = raw.get('name', '')
    elif isinstance(raw, list):
        records = raw
        name = ''
    else:
        raise ValueError(f'未知格式: {type(raw).__name__}')

    df = pd.DataFrame(records)

    # 字段归一化
    col_map = {
        'date': ['date', 'day', 'Date', 'Day'],
        'open': ['open', 'Open', 'o'],
        'high': ['high', 'High', 'h'],
        'low': ['low', 'Low', 'l'],
        'close': ['close', 'Close', 'c', 'closing'],
        'volume': ['volume', 'Volume', 'vol', 'Vol'],
    }

    cleaned = {}
    for target, candidates in col_map.items():
        for c in candidates:
            if c in df.columns:
                cleaned[target] = pd.to_numeric(df[c], errors='coerce') if target != 'date' else pd.to_datetime(df[c])
                break

    result = pd.DataFrame(cleaned)
    result['name'] = name
    return (result[result['close'] > 0]
            .drop_duplicates('date', keep='last')
            .sort_values('date')
            .reset_index(drop=True))


def load_weekly(code):
    """加载周线数据"""
    path = os.path.join(HISTORY_LONG, code + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        records = raw.get('records', raw.get('data', []))

    df = pd.DataFrame(records)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    elif 'day' in df.columns:
        df['date'] = pd.to_datetime(df.pop('day'))

    col_map = {'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c', 'volume': 'vol'}
    for dst, src in col_map.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = pd.to_numeric(df[src], errors='coerce')

    return (df[df['close'] > 0]
            .drop_duplicates('date', keep='last')
            .sort_values('date')
            .reset_index(drop=True))


def daily_to_monthly(df):
    """日线转月线"""
    df = df.copy()
    df['month'] = df['date'].dt.to_period('M')
    return (df.groupby('month').agg(
        date=('date', 'last'),
        open=('open', 'first'),
        high=('high', 'max'),
        low=('low', 'min'),
        close=('close', 'last'),
        volume=('volume', 'sum')
    ).reset_index().sort_values('date'))


def build_panel(pool, min_rows=400):
    """加载多只ETF并构建对齐面板"""
    data = {}
    for code in pool:
        try:
            df = load_etf(code)
            if len(df) >= min_rows:
                data[code] = df
        except Exception as e:
            pass
    common = sorted(set.intersection(*[set(d['date']) for d in data.values()]))
    panel = pd.DataFrame({'date': common}).set_index('date')
    for code, df in data.items():
        panel[code] = panel.index.map(df.set_index('date')['close'])
    return data, panel


# ════════════════════════════════════════
# 2. RSRS 算法
# ════════════════════════════════════════

def compute_rsrs(df, n=18, m=900, buy_thr=0.7, sell_thr=-1.0):
    """
    计算RSRS信号序列
    输入: df(含high/low columns), n(回归窗口), m(标准化窗口)
    输出: signal(Z>,1 买入; <-1 卖出), zscore(序列), beta(序列)
    """
    high, low = df['high'].values, df['low'].values
    beta = np.full(len(df), np.nan)
    for i in range(n - 1, len(df)):
        y = high[i - n + 1:i + 1]
        x = low[i - n + 1:i + 1]
        if not (np.isnan(x).any() or np.isnan(y).any()):
            xm = np.column_stack([np.ones(n), x])
            try:
                beta[i] = np.linalg.lstsq(xm, y, rcond=None)[0][1]
            except:
                pass
    zscore = np.full(len(beta), np.nan)
    for i in range(m - 1, len(beta)):
        v = beta[i - m + 1:i + 1]
        vv = v[~np.isnan(v)]
        if len(vv) >= 100:
            mu, sg = np.mean(vv), np.std(vv, ddof=1)
            if sg > 0:
                zscore[i] = (beta[i] - mu) / sg

    signal = np.zeros(len(zscore), dtype=int)
    pos = 0
    for i in range(len(zscore)):
        if not np.isnan(zscore[i]):
            if zscore[i] > buy_thr:
                pos = 1
            elif zscore[i] < sell_thr:
                pos = 0
        signal[i] = pos
    return signal, zscore, beta


# ════════════════════════════════════════
# 3. C63 复合动量
# ════════════════════════════════════════

def c63_score_for_date(close_series, date_idx, lookbacks=(50, 63, 75)):
    """单日C63动量评分"""
    rets = []
    for lb in lookbacks:
        if date_idx >= lb:
            r = close_series[date_idx] / close_series[date_idx - lb] - 1
            rets.append(r)
    return np.mean(rets) if rets else None


def compute_c63_panel(panel, lookbacks=(50, 63, 75)):
    """对整个面板计算每日C63动量"""
    scores = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    for i, date in enumerate(panel.index):
        for code in panel.columns:
            sc = c63_score_for_date(panel[code].values, i, lookbacks)
            if sc is not None:
                scores.loc[date, code] = sc
            else:
                scores.loc[date, code] = np.nan
    return scores


# ════════════════════════════════════════
# 4. 波动率仓位
# ════════════════════════════════════════

def compute_vol_scaling(df_hs300, panel_dates, vol_window=70, target_vol=0.16):
    """沪深300波动率缩放"""
    dfi = df_hs300.set_index('date')
    daily_ret = dfi['close'].pct_change().fillna(0)
    ann_vol = daily_ret.rolling(vol_window).std() * np.sqrt(252)
    scaling = (target_vol / ann_vol).clip(0.1, 1.0).fillna(1.0)
    return scaling[scaling.index.isin(set(panel_dates))]


# ════════════════════════════════════════
# 5. 估值分位 (Price/MA12 乖离率滚动分位)
# ════════════════════════════════════════

def val_score(close_arr, idx, window=252, min_w=126):
    """Price/MA12 乖离率滚动分位"""
    pma = close_arr / pd.Series(close_arr).rolling(12, min_periods=6).mean().values
    if idx < window:
        return 0.5
    w = pma[max(0, idx - window):idx]
    v = w[~np.isnan(w)]
    if len(v) < min_w:
        return 0.5
    return (v > pma[idx]).sum() / len(v)


def compute_valuation_panel(panel, window=252):
    """对整个面板计算每日估值分位"""
    val_df = pd.DataFrame(0.5, index=panel.index, columns=panel.columns)
    for i, date in enumerate(panel.index):
        for code in panel.columns:
            vals = panel[code].values
            val_df.loc[date, code] = val_score(vals, i, window)
    return val_df


# ════════════════════════════════════════
# 6. 12-1动量
# ════════════════════════════════════════

def momentum_12_1_scores(panel):
    """12-1动量（过去11月）— 用于月度截面排名"""
    # 转月频
    monthly = panel.resample('M').last()
    scores = {}
    for code in monthly.columns:
        vals = monthly[code].values
        if len(vals) < 13:
            scores[code] = np.nan
            continue
        p_start = vals[-13]
        p_end = vals[-2]
        if p_start > 0:
            scores[code] = p_end / p_start - 1
        else:
            scores[code] = np.nan
    return scores


# ════════════════════════════════════════
# 7. 策略引擎 (统一入口)
# ════════════════════════════════════════

class RSRSStrategy:
    """RSRS + C63复合动量 + 估值轮动 统一引擎"""

    def __init__(self, n=18, m=900, buy_thr=0.7, sell_thr=-1.0,
                 lookbacks=(50, 63, 75), vol_window=70, target_vol=0.16,
                 pool='default'):
        self.n = n
        self.m = m
        self.buy_thr = buy_thr
        self.sell_thr = sell_thr
        self.lookbacks = lookbacks
        self.vol_window = vol_window
        self.target_vol = target_vol

        if pool == 'default':
            self.pool = ETF_POOL
        elif pool == 'wide':
            self.pool = WIDE_POOL
        elif isinstance(pool, dict):
            self.pool = pool
        else:
            self.pool = ETF_POOL

        self.data = {}
        self.panel = None
        self.df_hs300 = None
        self.last_result = None

    def load_all(self, min_rows=400):
        """加载所有数据"""
        # HS300日线（RSRS专用）
        self.df_hs300 = load_etf('510300')

        # ETF池
        data, panel = build_panel(self.pool, min_rows)
        self.data = data
        self.panel = panel
        return data, panel

    def run(self, rebalance_days=42, top_n=1):
        """
        完整运行策略
        返回 dict:
          rsrs: {zscore, beta, signal, signal_text, date}
          momentum: {c63: {...}, top1: {code, name, score}, top2: {...}}
          valuation: {scores: {...}}
          portfolio: {holdings: [...], weights: [...], vol_scale, market_active}
          advice: str
        """
        if self.df_hs300 is None:
            self.load_all()

        # ── RSRS ──
        rsrs_signal, zscore, beta = compute_rsrs(
            self.df_hs300, self.n, self.m, self.buy_thr, self.sell_thr
        )
        valid = ~np.isnan(zscore)
        last_z = zscore[valid][-1]
        last_beta = beta[valid][-1]
        last_date = str(self.df_hs300['date'].values[valid][-1])[:10]
        sig = 1 if last_z > self.buy_thr else (0 if last_z < self.sell_thr else -1)
        sig_text = {1: '买入', 0: '卖出', -1: '观望'}[sig]

        # ── C63动量 ──
        mom = compute_c63_panel(self.panel, self.lookbacks)
        last_mom = mom.iloc[-1].dropna().sort_values(ascending=False)
        top_codes = last_mom.head(top_n).index.tolist()
        top_scores = last_mom.head(top_n).values.tolist()

        # ── 估值 ──
        val_df = compute_valuation_panel(self.panel)
        last_val = val_df.iloc[-1].dropna().sort_values(ascending=False)

        # ── 波动率 ──
        vol_scaling = compute_vol_scaling(self.df_hs300, self.panel.index,
                                          self.vol_window, self.target_vol)
        last_scale = float(vol_scaling.iloc[-1]) if len(vol_scaling) > 0 else 1.0

        # ── 组合 ──
        market_active = sig == 1
        if market_active and top_codes:
            holdings = top_codes
            weights = [last_scale / len(top_codes)] * len(top_codes)
        else:
            holdings = []
            weights = []

        # ── 建议 ──
        advices = []
        if sig == 1:
            advices.append(f'RSRS买入信号(Z={last_z:.2f})')
            cheapest = last_val.index[-1]
            cheapest_score = last_val.iloc[-1]
            if cheapest_score > 0.7:
                advices.append(f'{cheapest}低估(分位{cheapest_score:.0%})')
        elif sig == 0:
            advices.append(f'RSRS卖出信号(Z={last_z:.2f})，建议空仓')
        else:
            advices.append(f'RSRS观望(Z={last_z:.2f})')

        if not market_active:
            advices.append('空仓等待')

        self.last_result = {
            'date': last_date,
            'rsrs': {
                'zscore': round(float(last_z), 3),
                'beta': round(float(last_beta), 3),
                'signal': sig,
                'signal_text': sig_text,
                'params': {'n': self.n, 'm': self.m,
                           'buy_thr': self.buy_thr, 'sell_thr': self.sell_thr}
            },
            'momentum': {
                'c63_top': [
                    {'code': c, 'name': self.pool.get(c, ''),
                     'score': round(float(s), 4)}
                    for c, s in zip(top_codes, top_scores)
                ],
                'c63_all': {c: round(float(s), 4)
                           for c, s in last_mom.items()},
            },
            'valuation': {
                'scores': {self.pool.get(c, c): round(float(s), 3)
                          for c, s in last_val.items()},
                'cheapest': {'name': self.pool.get(last_val.index[-1], ''),
                             'score': round(float(last_val.iloc[-1]), 3)},
            },
            'portfolio': {
                'market_active': market_active,
                'holdings': [{'code': c, 'name': self.pool.get(c, ''),
                              'weight': round(w, 4)}
                            for c, w in zip(holdings, weights)] if holdings else [],
                'vol_scale': round(last_scale, 3),
                'total_position': round(last_scale if market_active else 0, 3),
            },
            'advice': ' | '.join(advices),
        }
        return self.last_result

    def to_json(self, output_path=None):
        """输出JSON"""
        if self.last_result is None:
            self.run()
        out = self.last_result
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        return out


# ════════════════════════════════════════
# 8. 独立运行
# ════════════════════════════════════════

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='RSRS策略引擎')
    parser.add_argument('--pool', default='default', help='ETF池: default/wide/wide_5')
    parser.add_argument('--n', type=int, default=18, help='RSRS N')
    parser.add_argument('--m', type=int, default=900, help='RSRS M')
    parser.add_argument('--buy', type=float, default=0.7, help='买入阈值')
    parser.add_argument('--sell', type=float, default=-1.0, help='卖出阈值')
    parser.add_argument('--rb', type=int, default=42, help='调仓周期')
    parser.add_argument('--top', type=int, default=1, help='Top N')
    parser.add_argument('--json', default=None, help='输出JSON路径')
    args = parser.parse_args()

    pool_map = {'default': None, 'wide': 'wide', 'wide_5': 'wide'}
    strat = RSRSStrategy(
        n=args.n, m=args.m, buy_thr=args.buy, sell_thr=args.sell,
        pool=pool_map.get(args.pool, args.pool)
    )
    result = strat.run(rebalance_days=args.rb, top_n=args.top)

    print(f'\n=== RSRS策略引擎 运行结果 ===')
    print(f'日期: {result["date"]}')
    print(f'RSRS: Z={result["rsrs"]["zscore"]}, 信号={result["rsrs"]["signal_text"]}')
    top = result['momentum']['c63_top']
    top_name = top[0]['name'] if top else '无'
    top_score = top[0]['score'] if top else 'N/A'
    print(f'动量Top1: {top_name} (score={top_score})')
    cheap = result['valuation']['cheapest']
    print(f'最便宜: {cheap["name"]} (分位{cheap["score"]})')
    print(f'仓位: {result["portfolio"]["total_position"]}')
    print(f'建议: {result["advice"]}')

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f'已保存: {args.json}')
