"""
RSRS+C63复合动量+波动率仓位管理 — 最终策略实现
===================================================
三层架构：
  Layer 1: RSRS大盘择时 (沪深300 High-Low回归z-score)
  Layer 2: C63复合动量选股 (50+63+75d等权, Top1)
  Layer 3: 波动率仓位管理 (沪深300 70d滚动波动率→目标16%)

使用方法:
  python rsrs_final_strategy.py                         # 跑默认参数
  python rsrs_final_strategy.py --pool v9_2016 --rb 42  # 指定池和调仓周期
  python rsrs_final_strategy.py --from 2022-07 --to 2025-12  # 指定时段
"""

import json, os, sys, argparse, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

# ────────────────────────────────
# 默认参数
# ────────────────────────────────
DEFAULT_POOL = {
    '510300': 'HS300',      # 宽基-大盘
    '510050': 'SH50',       # 宽基-超大蓝筹
    '159902': 'ZZSM100',    # 宽基-中盘
    '159949': 'CYB50',      # 宽基-成长
    '512100': 'ZZ1000',     # 宽基-小盘
    '159928': 'CONSUM',     # 行业-消费
    '512800': 'BANK',       # 行业-银行
    '512400': 'METAL',      # 行业-有色
    '512200': 'REALEST',    # 行业-地产
    '510160': 'INDUP',      # 行业-工业
    '518880': 'GOLD',       # 商品-黄金
    '159905': 'DIV',        # 策略-深红利
    '510810': 'SHGQ',       # 政策-上海国企
}

DATA_DIR = r'D:\QClaw_Trading\data\history'

# ────────────────────────────────
# 1. 数据加载
# ────────────────────────────────

def load_etf(code):
    """加载单只ETF日线数据，兼容两种格式"""
    path = os.path.join(DATA_DIR, code + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    # 格式A: {code, name, records: [{date, open, close, ...}]}
    if isinstance(raw, dict):
        records = raw['records']
    # 格式B: [{day, open, high, low, close, volume}, ...]
    elif isinstance(raw, list):
        records = raw
        # 统一字段名
        for r in records:
            if 'day' in r and 'date' not in r:
                r['date'] = r.pop('day')
            if 'volume' in r and 'vol' not in r:
                r['vol'] = r.pop('volume')
            # 字符串转数值
            for k in ('open','high','low','close'):
                if isinstance(r.get(k), str):
                    r[k] = float(r[k])
    else:
        raise ValueError(f'{code}: 未知数据格式 {type(raw).__name__}')
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['close'] > 0] \
           .drop_duplicates('date', keep='last') \
           .sort_values('date') \
           .reset_index(drop=True)
    return df


def build_panel(pool, min_rows=800):
    """加载多只ETF并构建对齐后的面板"""
    data = {}
    for code in pool:
        try:
            df = load_etf(code)
            if len(df) >= min_rows:
                data[code] = df
            else:
                print(f'  [跳过] {code} ({pool[code]}): 仅{len(df)}行, 不足{min_rows}')
        except Exception as e:
            print(f'  [跳过] {code}: {e}')
    
    if not data:
        raise ValueError('所有ETF加载失败，无法构建面板')
    
    common = sorted(set.intersection(*[set(d['date']) for d in data.values()]))
    if not common:
        raise ValueError('ETF间无共同交易日，请检查数据覆盖范围')
    
    panel = pd.DataFrame({'date': common}).set_index('date')
    for code, df in data.items():
        panel[code] = panel.index.map(df.set_index('date')['close'])
    
    return data, panel


# ────────────────────────────────
# 2. RSRS大盘择时
# ────────────────────────────────

def compute_rsrs(df, n=18, m=900, buy_thr=0.7, sell_thr=-1.0):
    """
    计算RSRS信号序列
    输入: df(沪深300日线), n(回归窗口), m(标准化窗口), buy_thr/sell_thr(阈值)
    输出: signal(0/1信号序列, 与df对齐)
    """
    high, low = df['high'].values, df['low'].values
    beta = np.full(len(df), np.nan)
    
    # 用 numpy lstsq 替代 statsmodels OLS（~10x 提速）
    for i in range(n - 1, len(df)):
        y = high[i - n + 1:i + 1]
        x = low[i - n + 1:i + 1]
        if not np.isnan(x).any() and not np.isnan(y).any():
            xmat = np.column_stack([np.ones(n), x])
            try:
                beta[i] = np.linalg.lstsq(xmat, y, rcond=None)[0][1]
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
    
    signal = np.zeros(len(zscore))
    pos = 0
    for i in range(len(zscore)):
        if not np.isnan(zscore[i]):
            if zscore[i] > buy_thr:
                pos = 1
            elif zscore[i] < sell_thr:
                pos = 0
        signal[i] = pos
    
    return signal, zscore, beta


# ────────────────────────────────
# 3. C63复合动量
# ────────────────────────────────

def compute_momentum(data, panel, lookbacks=None):
    """预计算每只ETF的复合动量"""
    if lookbacks is None:
        lookbacks = [50, 63, 75]
    
    ps = set(panel.index)
    mom_data = {}
    for code, df in data.items():
        dfi = df.set_index('date')
        d = {}
        for lb in lookbacks:
            d[f'ret_{lb}'] = dfi['close'].pct_change(lb)
        mom = pd.DataFrame(d)
        mom_data[code] = mom[mom.index.isin(ps)]
    return mom_data


def c63_score(mom_df, date):
    """
    计算某ETF在某日的C63复合动量得分
    C63 = (ret_50 + ret_63 + ret_75) / 3
    """
    r = mom_df.loc[date]
    total_ret = 0.0
    valid = 0
    for lb in (50, 63, 75):
        v = r.get(f'ret_{lb}', np.nan)
        if not pd.isna(v):
            total_ret += v
            valid += 1
    return total_ret / valid if valid > 0 else None


# ────────────────────────────────
# 4. 波动率仓位管理
# ────────────────────────────────

def compute_vol_scaling(df, panel_dates, vol_window=70, target_vol=0.16):
    """
    基于沪深300计算波动率缩放因子
    仓位 = min(目标波动率 / 滚动年化波动率, 1.0)
    """
    dfi = df.set_index('date')
    daily_ret = dfi['close'].pct_change().fillna(0)
    ann_vol = daily_ret.rolling(vol_window).std() * np.sqrt(252)
    scaling = (target_vol / ann_vol).clip(0.1, 0.9)   # 限制仓位在10%~90%
    scaling = scaling.fillna(1.0)
    return scaling[scaling.index.isin(set(panel_dates))]


# ────────────────────────────────
# 5. 策略运行
# ────────────────────────────────

def run_strategy(data, panel, rsrs_signal, rsrs_dates,
                 mom_data, rebalance_days=42, top_n=1,
                 vol_scaling=None):
    """
    完整策略回测
    返回: positions DataFrame (每日各ETF仓位)
    """
    n = len(panel)
    positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    
    # 将RSRS信号对齐到面板日期
    rsrs_dates_ns = rsrs_dates.astype('datetime64[ns]')
    panel_dates_ns = panel.index.values.astype('datetime64[ns]')
    sig_idx = np.searchsorted(rsrs_dates_ns, panel_dates_ns)
    sig_series = pd.Series(
        [rsrs_signal[i] if i < len(rsrs_signal) else 0 for i in sig_idx],
        index=panel.index
    )
    
    nr = None   # 下次调仓日
    holdings = []
    
    for i, date in enumerate(panel.index):
        market = int(sig_series.loc[date])
        scale = float(vol_scaling.loc[date]) if vol_scaling is not None else 1.0
        
        if not market or scale <= 0:
            holdings = []
            positions.loc[date] = 0
            nr = None
            continue
        
        if nr is None or date >= nr:
            # 选股：绝对动量过滤 + 相对动量排序
            candidates = []
            for code in panel.columns:
                score = c63_score(mom_data[code], date)
                if score is not None and score > 0:
                    candidates.append((code, score))
            
            candidates.sort(key=lambda x: -x[1])
            holdings = [c[0] for c in candidates[:top_n]] if candidates else []
            if not holdings:
                # 无正动量票时，重置nr让次日重试
                nr = None
            else:
                nr = panel.index[min(i + rebalance_days, n - 1)]
        
        if holdings:
            weight = scale / len(holdings)
            for code in holdings:
                positions.loc[date, code] = weight
    
    return positions


# ────────────────────────────────
# 6. 绩效分析
# ────────────────────────────────

def analyze_performance(panel, positions, label=''):
    """
    分析策略绩效，返回DataFrame与关键指标
    """
    daily_ret = panel.pct_change().fillna(0)
    strategy_ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)
    bh_ret = daily_ret.mean(axis=1)
    
    equity = (1 + strategy_ret).cumprod()
    bh_equity = (1 + bh_ret).cumprod()
    
    years = len(strategy_ret) / 252
    total_cagr = equity.iloc[-1] ** (1 / years) - 1
    total_sharpe = np.sqrt(252) * strategy_ret.mean() / strategy_ret.std() if strategy_ret.std() > 1e-10 else 0
    total_mdd = ((equity - equity.cummax()) / equity.cummax()).min()
    bh_cagr = bh_equity.iloc[-1] ** (1 / years) - 1
    
    annual_rows = []
    for yr in sorted(set(d.year for d in panel.index)):
        mask = panel.index.year == yr
        nd = mask.sum()
        if nd < 10:
            continue
        ys = strategy_ret[mask]
        yeq = (1 + ys).cumprod()
        cagr = yeq.iloc[-1] ** (252 / nd) - 1
        sh = np.sqrt(252) * ys.mean() / ys.std() if ys.std() > 1e-10 else 0
        mdd = ((yeq - yeq.cummax()) / yeq.cummax()).min()
        bh_c = (1 + bh_ret[mask]).cumprod().iloc[-1] ** (252 / nd) - 1
        annual_rows.append({
            'Year': yr, 'Strategy%': round(cagr * 100, 1),
            'BH%': round(bh_c * 100, 1), 'Excess%': round((cagr - bh_c) * 100, 1),
            'Sharpe': round(sh, 2), 'MDD%': round(mdd * 100, 1)
        })
    
    annual_df = pd.DataFrame(annual_rows)
    total_row = {
        'Year': 'TOTAL', 'Strategy%': round(total_cagr * 100, 1),
        'BH%': round(bh_cagr * 100, 1), 'Excess%': round((total_cagr - bh_cagr) * 100, 1),
        'Sharpe': round(total_sharpe, 2), 'MDD%': round(total_mdd * 100, 1)
    }
    
    # 选股统计
    sel_count = {}
    sel_dates = positions[positions.sum(axis=1) > 0]
    for date in sel_dates.index:
        for c in positions.columns:
            if positions.loc[date, c] > 0:
                sel_count[c] = sel_count.get(c, 0) + 1
    total_trade_days = len(sel_dates)
    
    return annual_df, total_row, strategy_ret, {'sel_count': sel_count, 'trade_days': total_trade_days}


# ────────────────────────────────
# 7. 主入口
# ────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='RSRS+C63+波动率 最终策略回测')
    # ETF池选择（当前仅支持 default）
    # parser.add_argument('--pool', ...)  # 预留
    parser.add_argument('--n', type=int, default=18, help='RSRS回归窗口')
    parser.add_argument('--m', type=int, default=900, help='RSRS标准化窗口')
    parser.add_argument('--buy', type=float, default=0.7, help='RSRS买入阈值')
    parser.add_argument('--sell', type=float, default=-1.0, help='RSRS卖出阈值')
    parser.add_argument('--rb', type=int, default=42, help='调仓周期(交易日)')
    parser.add_argument('--top', type=int, default=1, help='持有ETF数量')
    parser.add_argument('--vw', type=int, default=70, help='波动率窗口')
    parser.add_argument('--tv', type=float, default=0.16, help='目标年化波动率')
    parser.add_argument('--from', dest='start', default=None, help='起始日期 yyyy-mm-dd')
    parser.add_argument('--to', dest='end', default=None, help='结束日期 yyyy-mm-dd')
    args = parser.parse_args()
    
    print('=' * 60)
    print('  RSRS + C63复合动量 + 波动率仓位管理  V4 (最终方案)')
    print('=' * 60)
    print(f'\n  参数配置:')
    print(f'    RSRS:     N={args.n}, M={args.m}, buy={args.buy}, sell={args.sell}')
    print(f'    C63动量:  lookbacks=[50,63,75], Top{args.top}, rebalance={args.rb}d')
    print(f'    波动率:   窗口={args.vw}d, 目标={args.tv*100:.0f}%')
    
    # 加载数据
    print(f'\n  加载ETF数据...')
    data, panel = build_panel(DEFAULT_POOL)
    print(f'    共{len(DEFAULT_POOL)}只ETF, {len(panel)}个交易日')
    print(f'    日期范围: {panel.index[0].date()} ~ {panel.index[-1].date()}')
    
    # 截取日期范围
    if args.start:
        panel = panel[panel.index >= args.start]
    if args.end:
        panel = panel[panel.index <= args.end]
    print(f'    回测范围: {panel.index[0].date()} ~ {panel.index[-1].date()}')
    
    # RSRS计算
    print(f'\n  计算RSRS信号...')
    df510 = load_etf('510300')
    rsrs_signal, _, _ = compute_rsrs(df510, args.n, args.m, args.buy, args.sell)
    rsrs_dates = df510['date'].values
    
    # 复合动量
    print(f'  计算C63复合动量...')
    mom_data = compute_momentum(data, panel)
    
    # 波动率
    print(f'  计算波动率仓位缩放...')
    vol_scaling = compute_vol_scaling(df510, panel.index, args.vw, args.tv)
    avg_scale = vol_scaling.mean()
    full_scale_pct = (vol_scaling >= 0.99).mean() * 100
    print(f'    平均仓位: {avg_scale*100:.1f}%, 满仓比例: {full_scale_pct:.1f}%')
    
    # 运行策略
    print(f'\n  运行策略回测...')
    positions = run_strategy(data, panel, rsrs_signal, rsrs_dates,
                             mom_data, args.rb, args.top, vol_scaling)
    
    # 分析
    annual_df, total_row, strategy_ret, stats = analyze_performance(panel, positions)
    
    # 输出结果
    print(f'\n  ──── 分年度绩效 ────')
    print(f'  {"Year":<8} {"CAGR%":<8} {"BH%":<8} {"XS%":<8} {"Sharpe":<8} {"MDD%":<8}')
    print(f'  {"-"*48}')
    for _, row in annual_df.iterrows():
        yr = str(row['Year']) if row['Year'] != 2022 else f'{row["Year"]}*'
        print(f'  {yr:<8} {row["Strategy%"]:<8.1f} {row["BH%"]:<8.1f} {row["Excess%"]:<8.1f} {row["Sharpe"]:<8.2f} {row["MDD%"]:<8.1f}')
    print(f'  {"-"*48}')
    print(f'  {total_row["Year"]:<8} {total_row["Strategy%"]:<8.1f} {total_row["BH%"]:<8.1f} {total_row["Excess%"]:<8.1f} {total_row["Sharpe"]:<8.2f} {total_row["MDD%"]:<8.1f}')
    
    # RSRS信号统计
    pos_days = (positions.sum(axis=1) > 0).sum()
    total_days = len(positions)
    print(f'\n  ──── 持仓统计 ────')
    print(f'    持仓日: {pos_days}/{total_days} ({pos_days/total_days*100:.1f}%)')
    print(f'    空仓日: {total_days-pos_days}/{total_days} ({(total_days-pos_days)/total_days*100:.1f}%)')
    
    # 选股统计
    print(f'\n  ──── ETF持仓天数排名 ────')
    names = {**DEFAULT_POOL}
    for code in sorted(stats['sel_count'], key=lambda x: -stats['sel_count'][x]):
        pct = stats['sel_count'][code] / stats['trade_days'] * 100
        print(f'    {names.get(code, code):<12}: {stats["sel_count"][code]:>4}d ({pct:.1f}%)')
    
    # 持仓期分布
    holdings = positions[positions.sum(axis=1) > 0]
    holding_streaks = []
    streak = 0
    for date in positions.index:
        in_market = (positions.loc[date].sum() > 0)
        if in_market:
            streak += 1
        else:
            if streak > 0:
                holding_streaks.append(streak)
            streak = 0
    if streak > 0:
        holding_streaks.append(streak)
    
    if holding_streaks:
        print(f'\n  ──── 持仓期分布 ────')
        print(f'    最长: {max(holding_streaks)}d  最短: {min(holding_streaks)}d')
        print(f'    平均: {np.mean(holding_streaks):.0f}d  中位: {np.median(holding_streaks):.0f}d')
    
    print(f'\n  {"="*60}')

if __name__ == '__main__':
    main()
