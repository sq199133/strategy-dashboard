# -*- coding: utf-8 -*-
"""
12-1动量因子策略验证
====================
对比：
  - 普通12月动量（含当月）
  - 12-1动量（剔除最近1月）
  - 截面动量（月度排名） vs 时序动量（自身趋势）
  - 与RSRS v4的C63复合动量对比

数据：本地ETF历史（宽基+行业+商品）
区间：2018-01 ~ 2026-07（月频）
"""

import os, json, sys, warnings, argparse
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

DATA_DIR = r'D:\QClaw_Trading\data\history'

# 池配置（宽基为主）
ETF_POOL = {
    # 宽基
    '510300': '沪深300', '510500': '中证500', '512100': '中证1000',
    '159915': '创业板指', '588080': '科创50', '510050': '上证50',
    # 行业
    '159928': '消费', '512800': '银行', '512400': '有色',
    '512200': '地产', '510160': '工业',
    # 商品/策略
    '518880': '黄金', '159905': '红利',
}


# ────────────────────────────────
def load_etf(code):
    """加载ETF日线，返回月度数据"""
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
    if not dc or not cc:
        return None

    df['date'] = pd.to_datetime(df[dc])
    df['close'] = pd.to_numeric(df[cc], errors='coerce')
    df = df.dropna(subset=['date', 'close'])
    df = df[df['close'] > 0].drop_duplicates('date', keep='last').sort_values('date')

    # 转月频（月末收盘）
    df['month'] = df['date'].dt.to_period('M')
    monthly = df.groupby('month').agg(
        date=('date', 'last'),
        close=('close', 'last')
    ).reset_index()
    monthly['date'] = pd.to_datetime(monthly['date'])

    return monthly


def build_panel(codes):
    """构建对齐的月度面板"""
    frames = {}
    for code in codes:
        df = load_etf(code)
        if df is not None and len(df) >= 24:  # 至少2年数据
            frames[code] = df.set_index('month')
    if not frames:
        raise ValueError('无有效数据')

    # 对齐月份
    common = sorted(set.intersection(*[set(df.index) for df in frames.values()]))
    panel = pd.DataFrame({'month': common}).set_index('month')
    for code, df in frames.items():
        panel[code] = panel.index.map(df['close'])

    return frames, panel


def compute_momentum_12_1(monthly_prices):
    """
    12-1动量：过去12个月剔除最近1月
    输入：月度价格序列（12期）
    输出：前11个月收益率
    """
    if len(monthly_prices) < 12:
        return np.nan
    # T-12 到 T-1（不含T）
    p_start = monthly_prices.iloc[-13]  # T-12月末
    p_end = monthly_prices.iloc[-2]      # T-1月末
    if p_start <= 0:
        return np.nan
    return p_end / p_start - 1


def compute_momentum_12(monthly_prices):
    """普通12月动量（含当月）"""
    if len(monthly_prices) < 12:
        return np.nan
    p_start = monthly_prices.iloc[-12]
    p_end = monthly_prices.iloc[-1]
    if p_start <= 0:
        return np.nan
    return p_end / p_start - 1


# ────────────────────────────────
def backtest_cross_sectional(panel, top_n=1, lookback=12, exclude_recent=1):
    """
    截面动量策略（月度排名）
    exclude_recent=1: 12-1动量
    exclude_recent=0: 普通12月动量
    """
    n = len(panel)
    positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    monthly_ret = panel.pct_change()

    holdings = []
    for i, month in enumerate(panel.index):
        if i < lookback:
            continue

        # 计算所有ETF的动量得分
        scores = []
        for code in panel.columns:
            prices = panel[code].iloc[i-lookback:i+1]
            if exclude_recent == 1:
                # 12-1动量：剔除最近1月
                mom = compute_momentum_12_1(prices)
            else:
                # 普通12月动量
                mom = compute_momentum_12(prices)
            if not np.isnan(mom):
                scores.append((code, mom))

        # 选动量最强的Top N
        scores.sort(key=lambda x: -x[1])
        holdings = [c for c, _ in scores[:top_n]]

        if holdings:
            weight = 1.0 / len(holdings)
            for code in holdings:
                positions.loc[month, code] = weight

    # 计算收益
    strategy_ret = (monthly_ret * positions.shift(1).fillna(0)).sum(axis=1)
    return strategy_ret, positions


def backtest_time_series(panel, lookback=12, exclude_recent=1):
    """
    时序动量策略（自身趋势）
    单标的：动量>0持有，<0空仓
    """
    n = len(panel)
    positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    monthly_ret = panel.pct_change()

    for i, month in enumerate(panel.index):
        if i < lookback:
            continue

        for code in panel.columns:
            prices = panel[code].iloc[i-lookback:i+1]
            if exclude_recent == 1:
                mom = compute_momentum_12_1(prices)
            else:
                mom = compute_momentum_12(prices)

            if not np.isnan(mom) and mom > 0:
                positions.loc[month, code] = 1.0

    # 归一化（每期持仓和=1）
    row_sum = positions.sum(axis=1)
    row_sum[row_sum == 0] = 1.0
    positions = positions.div(row_sum, axis=0)

    strategy_ret = (monthly_ret * positions.shift(1).fillna(0)).sum(axis=1)
    return strategy_ret, positions


def backtest_c63(panel, lookbacks=(50, 63, 75)):
    """C63复合动量（日频近似，用月频）"""
    # 简化：用多周期平均动量
    monthly_ret = panel.pct_change()
    positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)

    # 换算：50日≈2.5月，63日≈3月，75日≈3.75月
    month_windows = [3, 4]  # 用3月和4月平均

    for i, month in enumerate(panel.index):
        if i < max(month_windows):
            continue

        scores = []
        for code in panel.columns:
            rets = []
            for m in month_windows:
                if i >= m:
                    r = panel[code].iloc[i] / panel[code].iloc[i-m] - 1
                    rets.append(r)
            if rets:
                avg_ret = np.mean(rets)
                if avg_ret > 0:
                    scores.append((code, avg_ret))

        scores.sort(key=lambda x: -x[1])
        holdings = [c for c, _ in scores[:1]]  # Top1

        if holdings:
            positions.loc[month, holdings[0]] = 1.0

    strategy_ret = (monthly_ret * positions.shift(1).fillna(0)).sum(axis=1)
    return strategy_ret, positions


def analyze_performance(returns, label=''):
    """绩效分析"""
    if len(returns) == 0:
        return None

    cum = (1 + returns).cumprod()
    years = len(returns) / 12
    ann = cum.iloc[-1] ** (1 / years) - 1 if years > 0 else 0
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()

    # 月度Sharpe（年化）
    if returns.std() > 0:
        sharpe = np.sqrt(12) * returns.mean() / returns.std()
    else:
        sharpe = 0

    win = (returns > 0).mean()

    return {
        'name': label,
        'ann': ann,
        'mdd': mdd,
        'sharpe': sharpe,
        'win': win,
        'n_months': len(returns),
    }


# ────────────────────────────────
def main():
    print('=' * 70)
    print('  12-1动量因子策略验证（A股ETF）')
    print('=' * 70)

    # 加载数据
    print(f'\n加载ETF池: {len(ETF_POOL)}只')
    frames, panel = build_panel(ETF_POOL.keys())
    print(f'面板: {panel.index[0]} ~ {panel.index[-1]}, {len(panel)}月')
    print(f'ETF: {list(panel.columns)}')

    # 基准
    monthly_ret = panel.pct_change()
    bh_ret = monthly_ret.mean(axis=1)  # 等权持有

    results = []

    # ────────────────────────────
    # 策略1: 截面12-1动量 Top1
    # ────────────────────────────
    print('\n运行策略...')
    print('  A_截面12-1动量Top1...', end='', flush=True)
    ret_a, pos_a = backtest_cross_sectional(panel, top_n=1, lookback=12, exclude_recent=1)
    r_a = analyze_performance(ret_a[ret_a.index >= panel.index[12]], 'A_截面12-1Top1')
    results.append(r_a)
    print(f' ann={r_a["ann"]*100:.1f}% Sharpe={r_a["sharpe"]:.2f}')

    # 策略2: 截面普通12月动量 Top1
    print('  B_截面12月动量Top1...', end='', flush=True)
    ret_b, pos_b = backtest_cross_sectional(panel, top_n=1, lookback=12, exclude_recent=0)
    r_b = analyze_performance(ret_b[ret_b.index >= panel.index[12]], 'B_截面12月Top1')
    results.append(r_b)
    print(f' ann={r_b["ann"]*100:.1f}% Sharpe={r_b["sharpe"]:.2f}')

    # 策略3: 截面12-1动量 Top2
    print('  C_截面12-1动量Top2...', end='', flush=True)
    ret_c, pos_c = backtest_cross_sectional(panel, top_n=2, lookback=12, exclude_recent=1)
    r_c = analyze_performance(ret_c[ret_c.index >= panel.index[12]], 'C_截面12-1Top2')
    results.append(r_c)
    print(f' ann={r_c["ann"]*100:.1f}% Sharpe={r_c["sharpe"]:.2f}')

    # 策略4: 时序12-1动量
    print('  D_时序12-1动量...', end='', flush=True)
    ret_d, pos_d = backtest_time_series(panel, lookback=12, exclude_recent=1)
    r_d = analyze_performance(ret_d[ret_d.index >= panel.index[12]], 'D_时序12-1')
    results.append(r_d)
    print(f' ann={r_d["ann"]*100:.1f}% Sharpe={r_d["sharpe"]:.2f}')

    # 策略5: 时序普通12月动量
    print('  E_时序12月动量...', end='', flush=True)
    ret_e, pos_e = backtest_time_series(panel, lookback=12, exclude_recent=0)
    r_e = analyze_performance(ret_e[ret_e.index >= panel.index[12]], 'E_时序12月')
    results.append(r_e)
    print(f' ann={r_e["ann"]*100:.1f}% Sharpe={r_e["sharpe"]:.2f}')

    # 策略6: C63复合动量（对比）
    print('  F_C63复合动量...', end='', flush=True)
    ret_f, pos_f = backtest_c63(panel)
    r_f = analyze_performance(ret_f[ret_f.index >= panel.index[4]], 'F_C63复合动量')
    results.append(r_f)
    print(f' ann={r_f["ann"]*100:.1f}% Sharpe={r_f["sharpe"]:.2f}')

    # 基准
    r_bh = analyze_performance(bh_ret[bh_ret.index >= panel.index[12]], 'G_等权持有')
    results.append(r_bh)

    # ────────────────────────────
    # 打印结果
    # ────────────────────────────
    print('\n' + '=' * 70)
    print('  12-1动量因子策略对比（月频，2018-2026）')
    print('=' * 70)
    print(f"{'策略':<20}{'年化':>8}{'Sharpe':>8}{'MDD':>8}{'胜率':>7}")
    print('-' * 70)
    for r in sorted(results, key=lambda x: -x['sharpe']):
        print(f"{r['name']:<20}{r['ann']*100:>7.1f}%{r['sharpe']:>7.2f}{r['mdd']*100:>7.1f}%{r['win']*100:>6.1f}%")

    # ────────────────────────────
    # 分析：12-1 vs 12月
    # ────────────────────────────
    print('\n--- 关键对比 ---')
    print('截面动量：')
    diff_ann = (r_a['ann'] - r_b['ann']) * 100
    diff_sharpe = r_a['sharpe'] - r_b['sharpe']
    print(f'  12-1动量: {r_a["ann"]*100:.1f}% / Sharpe {r_a["sharpe"]:.2f}')
    print(f'  12月动量: {r_b["ann"]*100:.1f}% / Sharpe {r_b["sharpe"]:.2f}')
    print(f'  差异: {diff_ann:+.1f}%年化, {diff_sharpe:+.2f} Sharpe')

    print('\n时序动量：')
    diff_ann2 = (r_d['ann'] - r_e['ann']) * 100
    diff_sharpe2 = r_d['sharpe'] - r_e['sharpe']
    print(f'  12-1动量: {r_d["ann"]*100:.1f}% / Sharpe {r_d["sharpe"]:.2f}')
    print(f'  12月动量: {r_e["ann"]*100:.1f}% / Sharpe {r_e["sharpe"]:.2f}')
    print(f'  差异: {diff_ann2:+.1f}%年化, {diff_sharpe2:+.2f} Sharpe')

    # ────────────────────────────
    # 12-1的核心优势验证
    # ────────────────────────────
    print('\n--- 12-1动量核心优势验证 ---')

    # 1. 检查短期反转效应
    print('\n1. 短期反转效应（1月涨幅 vs 未来1月收益）')
    short_ret = monthly_ret.shift(-1)  # 未来1月收益
    mom1 = panel.pct_change(1)         # 当前1月涨幅
    corr = mom1.iloc[:-1].corrwith(short_ret.iloc[:-1], axis=0).mean()
    print(f'   1月涨幅 vs 未来1月收益 相关系数: {corr:.4f}')
    if corr < -0.05:
        print('   → 存在显著短期反转（涨得多的下月跌）')
    elif corr < 0.05:
        print('   → 短期反转较弱')
    else:
        print('   → 短期动量延续（涨得多的继续涨）')

    # 2. 检查中长期趋势延续
    print('\n2. 中长期趋势延续（11月涨幅 vs 未来1月收益）')
    mom11 = panel.pct_change(11).shift(1)  # 前11月涨幅（剔除当月）
    corr11 = mom11.iloc[:-1].corrwith(short_ret.iloc[:-1], axis=0).mean()
    print(f'   前11月涨幅 vs 未来1月收益 相关系数: {corr11:.4f}')
    if corr11 > 0.05:
        print('   → 存在中长期动量效应')
    else:
        print('   → 中长期动量较弱')

    # 3. 回撤对比
    print('\n3. 回撤对比')
    print(f'   12-1截面 MDD: {r_a["mdd"]*100:.1f}%')
    print(f'   12月截面 MDD: {r_b["mdd"]*100:.1f}%')
    print(f'   改善: {(r_b["mdd"] - r_a["mdd"])*100:+.1f}%')

    print('\n' + '=' * 70)
    print('  结论：')
    if r_a['sharpe'] > r_b['sharpe'] and r_a['mdd'] > r_b['mdd']:
        print('  12-1动量优于12月动量（Sharpe更高 + 回撤更小）')
    elif r_a['sharpe'] > r_b['sharpe']:
        print('  12-1动量Sharpe更高，但回撤未改善')
    else:
        print('  12-1动量未显示优势')
    print('=' * 70)


if __name__ == '__main__':
    main()
