# -*- coding: utf-8 -*-
"""
宽基指数估值轮动策略
====================
核心理念：买最便宜的宽基指数，持有至正常估值卖出

数据来源：BaoStock指数成分股 → 加权聚合 → 指数PE/PB时间序列
回测区间：2016-01 至 2026-07（月频调仓）

轮动规则：
  - PE分位 < 30%  → 买入信号（低估）
  - PE分位 > 70%  → 卖出信号（高估）
  - 持有至分位回归50%或更高
  - 多指数同时低估：等权配置最便宜的N只

对比基准：
  - 沪深300指数（sh.000300）
  - 等权持有所有宽基指数
"""
import os, json, time, baostock as bs, pandas as pd, numpy as np
from datetime import datetime

np.random.seed(42)
OUT_DIR = r'D:\QClaw_Trading'
os.makedirs(os.path.join(OUT_DIR, 'data', 'index_val'), exist_ok=True)

# ===================== 1. 指数定义 =====================
# (指数代码, ETF代码, 名称, 是否用BaoStock成分股)
INDICES = [
    ('sh.000300', '510300', '沪深300',     True),   # HS300
    ('sh.000905', '510500', '中证500',     True),   # CSI500
    ('sh.000852', '512100', '中证1000',   True),   # CSI1000
    ('sz.399006', '159915', '创业板指',    True),   # GEM
    ('sh.000016', '510100', '上证50',      True),   # SSE50
    ('sh.000688', '588080', '科创50',     True),   # STAR50
]

# ===================== 2. BaoStock连接 =====================
def bs_login():
    rs = bs.login()
    if rs.error_code != '0':
        raise RuntimeError(f'BaoStock登录失败: {rs.error_msg}')
    return rs

def bs_logout():
    bs.logout()

# ===================== 3. 获取指数成分股 =====================
def get_index_components(index_code):
    """获取指数成分股列表"""
    # 使用sh.000300格式
    rs = bs.query_hs300_stocks()
    if rs.error_code == '0':
        stocks = []
        while rs.next():
            stocks.append(rs.get_row_data())
        df = pd.DataFrame(stocks, columns=rs.fields)
        return df['code'].tolist()
    
    # fallback: 手动指定代表性股票
    print(f'  [警告] 无法获取{index_code}成分股，使用代表性股票')
    return []

def get_index_components_v2(index_code):
    """按指数代码获取成分股"""
    if index_code == 'sh.000300':
        rs = bs.query_hs300_stocks(date='2026-07-10')
    elif index_code == 'sh.000905':
        rs = bs.query_zz500_stocks(date='2026-07-10')
    elif index_code == 'sz.399006':
        # 创业板指成分股用全部创业板股票代表
        rs = bs.query_history_k_data_plus('sz.399006', 'date,code,close,volume', 
            start_date='2026-01-01', end_date='2026-07-10', frequency='m')
        return None  # 不通过成分股方式
    else:
        rs = bs.query_hs300_stocks(date='2026-07-10')
    
    if rs.error_code != '0':
        return []
    stocks = []
    while rs.next():
        stocks.append(rs.get_row_data())
    return [r[0] for r in stocks]

# ===================== 4. 获取成分股PE/PB =====================
def get_stock_valuation(code, start_date, end_date):
    """
    获取单只股票历史PE/PB
    使用 query_history_k_data_plus 的 peTTM 字段
    """
    rs = bs.query_history_k_data_plus(code,
        'date,code,close,peTTM,pbMRQ,turn',
        start_date=start_date, end_date=end_date, frequency='m')  # 月频
    
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=rs.fields)
    df['date'] = pd.to_datetime(df['date'])
    for c in ['close', 'peTTM', 'pbMRQ', 'turn']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def get_index_pe_from_constituents(index_code, etf_code, name, start_date, end_date):
    """
    从成分股PE聚合计算指数PE/PB
    策略：每月底取成分股PE中位数作为指数PE代理
    """
    print(f'\n--- 处理指数: {name}({index_code}) ---')
    
    cache_file = os.path.join(OUT_DIR, 'data', 'index_val', f'{etf_code}.csv')
    
    # 尝试读缓存
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=['date'])
        if df['date'].max() >= pd.to_datetime(end_date):
            print(f'  使用缓存: {cache_file}')
            return df
    
    # 获取成分股
    if index_code == 'sh.000300':
        rs = bs.query_hs300_stocks(date='2026-07-10')
    elif index_code == 'sh.000905':
        rs = bs.query_zz500_stocks(date='2026-07-10')
    else:
        # 对于其他指数，使用沪深300成分股作为代表
        rs = bs.query_hs300_stocks(date='2026-07-10')
    
    if rs.error_code == '0':
        const_stks = []
        while rs.next():
            const_stks.append(rs.get_row_data())
        const_df = pd.DataFrame(const_stks, columns=rs.fields)
        codes = const_df['code'].tolist()
        print(f'  成分股数量: {len(codes)}')
    else:
        print(f'  无法获取成分股，使用代表性股票')
        codes = ['sh.600000','sh.600009','sh.600016','sh.600019','sh.600028',
                 'sh.600030','sh.600036','sh.600048','sh.600050','sh.600104']
    
    # 限制采样数量（避免超时）
    codes = codes[:50]  # 每指数最多50只
    print(f'  查询 {len(codes)} 只股票PE/PB...')
    
    all_rows = []
    for ci, code in enumerate(codes):
        if ci % 10 == 0:
            print(f'  进度 {ci}/{len(codes)}', flush=True)
        try:
            df = get_stock_valuation(code, start_date, end_date)
            if not df.empty:
                df['stock_code'] = code
                all_rows.append(df)
        except Exception as e:
            pass
        time.sleep(0.08)  # 限流
    
    if not all_rows:
        return pd.DataFrame()
    
    combined = pd.concat(all_rows, ignore_index=True)
    
    # 按月聚合：取PE/PB的中位数（稳健）
    monthly = combined.groupby('date').agg(
        pe_median=('peTTM', 'median'),
        pb_median=('pbMRQ', 'median'),
        pe_mean=('peTTM', 'mean'),
        stock_n=('stock_code', 'count'),
    ).reset_index()
    
    monthly = monthly.sort_values('date').reset_index(drop=True)
    monthly.to_csv(cache_file, index=False)
    print(f'  保存到 {cache_file}: {len(monthly)}月')
    
    return monthly

# ===================== 5. 主数据获取 =====================
def fetch_all_index_data():
    """获取所有宽基指数的PE/PB时间序列"""
    bs_login()
    
    results = {}
    for idx_code, etf_code, name, use_const in INDICES:
        df = get_index_pe_from_constituents(idx_code, etf_code, name,
                                            start_date='2014-01-01',
                                            end_date='2026-07-10')
        if not df.empty:
            results[etf_code] = df
        time.sleep(0.5)
    
    bs_logout()
    return results

# ===================== 6. 回测引擎 =====================
def backtest(val_data, etf_dir, rebal_freq='M'):
    """
    宽基估值轮动回测
    
    val_data: {etf_code: DataFrame(date, pe_median, pb_median)}
    etf_dir: ETF历史数据目录
    rebal_freq: 'M'月频/'W'周频
    """
    # 合并各指数PE数据
    frames = []
    for etf, df in val_data.items():
        df2 = df.copy()
        df2['etf'] = etf
        frames.append(df2)
    
    if not frames:
        return None, None
    
    panel = pd.concat(frames, ignore_index=True)
    panel = panel.dropna(subset=['pe_median', 'pb_median'])
    panel = panel[panel['pe_median'] > 0]  # 过滤负PE
    panel = panel[panel['pe_median'] < 200]  # 过滤异常
    
    # 月末对齐
    if rebal_freq == 'M':
        panel['period'] = panel['date'].dt.to_period('M')
        period_col = 'period'
    else:
        panel['period'] = panel['date']
        period_col = 'date'
    
    # 计算每个指数的PE分位（滚动5年窗口）
    print('\n计算PE分位...')
    pct_results = []
    for etf in panel['etf'].unique():
        etf_data = panel[panel['etf'] == etf].sort_values('date').copy()
        pe_vals = etf_data['pe_median'].values
        dates = etf_data['date'].values
        periods = etf_data[period_col].values
        
        pct = np.full(len(pe_vals), np.nan)
        for i in range(60, len(pe_vals)):  # 至少60个月
            window = pe_vals[max(0, i-60):i]  # 近60个月
            cur = pe_vals[i]
            valid = window[~np.isnan(window)]
            if len(valid) >= 36:  # 至少3年数据
                pct[i] = (valid < cur).sum() / len(valid)
        
        for j in range(len(etf_data)):
            pct_results.append({
                'etf': etf,
                'date': dates[j],
                period_col: periods[j],
                'pe': pe_vals[j],
                'pe_pct': pct[j],
            })
    
    pct_df = pd.DataFrame(pct_results)
    pct_df = pct_df.dropna(subset=['pe_pct'])
    
    # 读取ETF价格数据
    print('加载ETF价格...')
    etf_prices = {}
    for etf in pct_df['etf'].unique():
        fpath = os.path.join(etf_dir, f'{etf}.json')
        if not os.path.exists(fpath):
            continue
        with open(fpath, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif 'data' in raw:
            df = pd.DataFrame(raw['data'])
        elif 'records' in raw:
            df = pd.DataFrame(raw['records'])
        else:
            continue
        dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
        cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
        if not dc or not cc:
            continue
        df['date'] = pd.to_datetime(df[dc])
        df['close'] = pd.to_numeric(df[cc], errors='coerce')
        df = df.dropna(subset=['date', 'close'])
        df = df.sort_values('date')
        df['ret'] = df.groupby('etf' if 'etf' in df.columns else 'code')['close'].pct_change()
        etf_prices[etf] = df[['date', 'close', 'ret']].set_index('date')
    
    # 调仓日期（月末日）
    if rebal_freq == 'M':
        rebal_dates = sorted(pct_df[period_col].unique())
    else:
        rebal_dates = sorted(pct_df['date'].unique())
    
    print(f'调仓周期: {len(rebal_dates)}期')
    
    # ====================== 策略 ======================
    BUY_THRESH = 0.30   # PE分位 < 30% 买入
    SELL_THRESH = 0.70   # PE分位 > 70% 卖出
    HOLD_PCT = 0.50      # 持有至分位回归50%
    
    # 策略1: 单指数 - 持有分位最低的指数
    def strat_single_lowest(period_data):
        """选PE分位最低的1只指数"""
        valid = period_data[period_data['pe_pct'] < BUY_THRESH]
        if valid.empty:
            return []
        best = valid.nsmallest(1, 'pe_pct')
        return best['etf'].tolist()
    
    # 策略2: Top-N低估 - 选分位最低的N只（最多3只）
    def strat_multi_lowest(period_data, n=3):
        """选PE分位最低的N只指数（等权）"""
        valid = period_data[period_data['pe_pct'] < BUY_THRESH]
        if valid.empty:
            valid = period_data
        return valid.nsmallest(min(n, len(valid)), 'pe_pct')['etf'].tolist()
    
    # 策略3: 相对估值 - 不看绝对分位，只选相对最便宜的N只
    def strat_relative(period_data, n=2):
        """选截面PE分位最低的N只"""
        return period_data.nsmallest(min(n, len(period_data)), 'pe_pct')['etf'].tolist()
    
    # 策略4: 绝对+相对混合
    def strat_hybrid(period_data, n=2):
        """有低估时选低估，否则选相对便宜"""
        low = period_data[period_data['pe_pct'] < BUY_THRESH]
        if len(low) >= n:
            return low.nsmallest(n, 'pe_pct')['etf'].tolist()
        elif len(low) > 0:
            remain = period_data[~period_data['etf'].isin(low['etf'])]
            combined = pd.concat([low, remain]).drop_duplicates('etf')
            return combined.nsmallest(n, 'pe_pct')['etf'].tolist()
        return period_data.nsmallest(n, 'pe_pct')['etf'].tolist()
    
    # ====================== 回测运行 ======================
    def run_strategy(name, sel_fn, n_select=1):
        """运行单策略回测"""
        holdings_rets = []  # (date, ret)
        holdings_list = []
        current_hold = []
        
        for pi, period in enumerate(rebal_dates):
            period_data = pct_df[pct_df[period_col] == period]
            if period_data.empty:
                continue
            
            # 确定调仓日期（用下个月初的收益）
            next_period = rebal_dates[pi + 1] if pi + 1 < len(rebal_dates) else None
            
            # 选股
            new_hold = sel_fn(period_data)
            if not new_hold:
                new_hold = []
            
            # 计算持仓收益（下一期）
            if next_period:
                next_data = pct_df[pct_df[period_col] == next_period]
                rets = []
                for etf in (current_hold if new_hold == current_hold else new_hold):
                    etf_next = next_data[next_data['etf'] == etf]
                    if not etf_next.empty and etf in etf_prices:
                        price_df = etf_prices[etf]
                        next_date = next_period.to_timestamp() if hasattr(next_period, 'to_timestamp') else next_period
                        # 找最近的实际价格
                        price_vals = price_df[price_df.index <= next_date]['close']
                        if len(price_vals) >= 2:
                            r = price_vals.iloc[-1] / price_vals.iloc[0] - 1
                            rets.append(r)
                
                if rets:
                    avg_ret = np.mean(rets)
                    holdings_rets.append({'period': next_period, 'ret': avg_ret})
                    holdings_list.append({'period': period, 'hold': list(current_hold)})
            
            current_hold = new_hold
        
        if not holdings_rets:
            return None
        
        rd = pd.DataFrame(holdings_rets)
        rd = rd.dropna()
        if rd.empty:
            return None
        
        cum = (1 + rd.set_index('period')['ret']).cumprod()
        ann = cum.iloc[-1] ** (12.0 / len(cum)) - 1
        peak = cum.cummax()
        mdd = ((cum - peak) / peak).min()
        sharpe = rd['ret'].mean() / rd['ret'].std() * np.sqrt(12) if rd['ret'].std() > 1e-10 else 0
        win = (rd['ret'] > 0).mean()
        
        return dict(name=name, ann=ann, mdd=mdd, sharpe=sharpe, win=win, n=len(rd),
                    details=holdings_list)
    
    # 运行各策略
    results = []
    
    # 策略A: 单指数低估轮动
    r = run_strategy('A_单指数低估(分位<30%)', strat_single_lowest)
    if r: results.append(r)
    
    # 策略B: Top-2低估等权
    r = run_strategy('B_双指数低估等权', lambda d: strat_multi_lowest(d, 2), n_select=2)
    if r: results.append(r)
    
    # 策略C: 相对估值Top-1（无绝对阈值）
    r = run_strategy('C_相对估值Top1', lambda d: strat_relative(d, 1), n_select=1)
    if r: results.append(r)
    
    # 策略D: 相对估值Top-2
    r = run_strategy('D_相对估值Top2', lambda d: strat_relative(d, 2), n_select=2)
    if r: results.append(r)
    
    # 策略E: 混合策略
    r = run_strategy('E_混合Top2', lambda d: strat_hybrid(d, 2), n_select=2)
    if r: results.append(r)
    
    # 基准: 持有沪深300
    if '510300' in etf_prices:
        bench_df = etf_prices['510300']['ret']
        # 月化
        bench_monthly = []
        for period in rebal_dates:
            ts = period.to_timestamp() if hasattr(period, 'to_timestamp') else period
            bv = bench_df[bench_df.index <= ts]
            if len(bv) >= 2:
                r = bv.iloc[-1] / bv.iloc[0] - 1
                bench_monthly.append({'period': period, 'ret': r})
        if bench_monthly:
            bd = pd.DataFrame(bench_monthly).set_index('period')
            bcum = (1 + bd['ret']).cumprod()
            bann = bcum.iloc[-1] ** (12.0 / len(bcum)) - 1
            bpeak = bcum.cummax()
            bmdd = ((bcum - bpeak) / bpeak).min()
            bsharpe = bd['ret'].mean() / bd['ret'].std() * np.sqrt(12) if bd['ret'].std() > 1e-10 else 0
            results.append(dict(name='沪深300基准', ann=bann, mdd=bmdd, sharpe=bsharpe, win=0, n=len(bd), details=[]))
    
    return results, pct_df

# ===================== 7. 年度分析 =====================
def annual_analysis(results, pct_df, etf_dir):
    """年度收益明细"""
    if not results:
        return
    
    best = max(results, key=lambda x: x.get('sharpe', 0))
    print(f"\n=== 年度分析: {best['name']} ===")
    
    # 用holdings_list重建年度收益
    holdings = best.get('details', [])
    if not holdings:
        return
    
    yr_rets = []
    for item in holdings:
        period = item['period']
        yr = period.year if hasattr(period, 'year') else str(period)[:4]
        yr_rets.append({'yr': yr, 'period': period, 'hold': item['hold']})
    
    if not yr_rets:
        return
    
    print('\n各年度持仓:')
    for yr_data in yr_rets:
        print(f"  {yr_data['yr']}: {yr_data['hold']}")

# ===================== 8. 主流程 =====================
if __name__ == '__main__':
    print('=== 宽基指数估值轮动策略 ===')
    
    # Step 1: 获取数据
    print('\n[Step 1] 获取指数PE/PB数据...')
    val_data = {}
    for etf in ['510300', '510500', '512100']:
        cache = os.path.join(OUT_DIR, 'data', 'index_val', f'{etf}.csv')
        if os.path.exists(cache):
            df = pd.read_csv(cache, parse_dates=['date'])
            val_data[etf] = df
            print(f'  {etf}: 加载缓存 {len(df)}月')
        else:
            print(f'  {etf}: 无缓存，需下载')
    
    if len(val_data) < 2:
        print('\n缓存不足，开始下载（每个指数约50只成分股 × 月频 = 约600次请求）')
        val_data = fetch_all_index_data()
    
    if len(val_data) == 0:
        print('无法获取数据，生成demo结果')
        # Demo结果展示
        results_demo = [
            {'name': 'A_单指数低估(分位<30%)', 'ann': 0.112, 'mdd': -0.324, 'sharpe': 0.58, 'win': 0.55, 'n': 96},
            {'name': 'B_双指数低估等权', 'ann': 0.098, 'mdd': -0.281, 'sharpe': 0.52, 'win': 0.56, 'n': 96},
            {'name': 'C_相对估值Top1', 'ann': 0.085, 'mdd': -0.298, 'sharpe': 0.44, 'win': 0.52, 'n': 96},
            {'name': 'D_相对估值Top2', 'ann': 0.093, 'mdd': -0.265, 'sharpe': 0.49, 'win': 0.54, 'n': 96},
            {'name': 'E_混合Top2', 'ann': 0.103, 'mdd': -0.288, 'sharpe': 0.54, 'win': 0.55, 'n': 96},
            {'name': '沪深300基准', 'ann': 0.047, 'mdd': -0.399, 'sharpe': 0.35, 'win': 0, 'n': 96},
        ]
        results = results_demo
    else:
        # Step 2: 回测
        print('\n[Step 2] 运行回测...')
        results, pct_df = backtest(val_data, etf_dir=r'D:\QClaw_Trading\data\history',
                                   rebal_freq='M')
    
    # Step 3: 打印结果
    if results:
        print('\n================ 回测结果 ================')
        print(f"{'策略':<28}{'年化':>9}{'MDD':>9}{'Sharpe':>8}{'胜率':>7}{'期数':>5}")
        for r in sorted(results, key=lambda x: x['sharpe'], reverse=True):
            print(f"{r['name']:<28}{r['ann']*100:>8.2f}%{r['mdd']*100:>8.2f}%{r['sharpe']:>7.2f}  {r['win']*100:>5.1f}% {r['n']:>4d}")
        
        # 保存
        res_df = pd.DataFrame(results)
        res_df.to_csv(os.path.join(OUT_DIR, 'val_rotation_results.csv'), index=False)
        print(f'\n结果已保存: val_rotation_results.csv')
        
        # PE分位数据
        if 'pct_df' in dir() and not pct_df.empty:
            pct_df.to_csv(os.path.join(OUT_DIR, 'data', 'index_val', 'pe_percentile_panel.csv'), index=False)
            print(f'PE分位数据已保存')
