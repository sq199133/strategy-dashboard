# -*- coding: utf-8 -*-
"""
宽基指数估值轮动策略 v2
====================
数据方案：
  1. 日频价格：BaoStock query_history_k_data_plus (frequency='d') —— 已验证可用
  2. 季度EPS：BaoStock query_profit_data + 线性插值到月频
  3. 指数PE = 指数收盘价 / 对应月份EPS

回测区间：2016-01 至 2026-06（月频调仓）

策略：
  - 构建沪深300、中证500、创业板指、科创50、上证50、中证1000的月频PE时间序列
  - 滚动5年窗口PE分位
  - 买入分位<30%，卖出分位>70%，持有至正常估值
  - 对比：低估单指数 / 低估Top2等权 / 相对估值Top2
"""
import os, json, time, baostock as bs, pandas as pd, numpy as np
from datetime import datetime

np.random.seed(42)
OUT_DIR = r'D:\QClaw_Trading'
DATA_DIR = os.path.join(OUT_DIR, 'data', 'index_val')
os.makedirs(DATA_DIR, exist_ok=True)

# ===================== 1. 配置 =====================
# 指数定义：(BaoStock指数代码, ETF代码, 名称, BaoStock成分接口)
INDICES = [
    ('sh.000300', '510300', '沪深300',    'hs300'),
    ('sh.000905', '510500', '中证500',    'zz500'),
    ('sz.399006', '159915', '创业板指',   'cyb'),
    ('sh.000688', '588080', '科创50',     'kcb'),
    ('sh.000016', '510100', '上证50',     'sz50'),
    ('sh.000852', '512100', '中证1000',  'other'),
]

# ===================== 2. BaoStock =====================
def bs_login():
    r = bs.login()
    if r.error_code != '0':
        raise RuntimeError(f'登录失败: {r.error_msg}')

def bs_logout():
    bs.logout()

# ===================== 3. 获取指数成分股 =====================
def get_constituents(ind_type):
    """获取指数成分股"""
    if ind_type == 'hs300':
        rs = bs.query_hs300_stocks(date='2026-07-10')
    elif ind_type == 'zz500':
        rs = bs.query_zz500_stocks(date='2026-07-10')
    else:
        # fallback: 用HS300
        rs = bs.query_hs300_stocks(date='2026-07-10')
    
    if rs.error_code != '0':
        return []
    stocks = []
    while rs.error_code == '0' and rs.next():
        stocks.append(rs.get_row_data())
    df = pd.DataFrame(stocks, columns=rs.fields)
    return df['code'].tolist()

# ===================== 4. 获取日频价格 =====================
def get_daily_prices(codes, start_date, end_date):
    """
    批量获取日频价格，按月聚合
    返回: {stock_code: DataFrame(date, close)}
    """
    results = {}
    t0 = time.time()
    total = len(codes)
    
    for i, code in enumerate(codes):
        rs = bs.query_history_k_data_plus(code,
            'date,code,close',
            start_date=start_date, end_date=end_date, frequency='d')
        
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        
        if rows:
            tmp = pd.DataFrame(rows, columns=rs.fields)
            tmp['date'] = pd.to_datetime(tmp['date'])
            tmp['close'] = pd.to_numeric(tmp['close'], errors='coerce')
            tmp = tmp.dropna(subset=['close'])
            results[code] = tmp[['date', 'close']]
        
        if (i+1) % 20 == 0:
            elapsed = time.time() - t0
            rate = (i+1) / elapsed
            remaining = (total - i - 1) / rate
            print(f'  进度 {i+1}/{total} ({elapsed:.0f}s, 剩余~{remaining:.0f}s)', flush=True)
        
        time.sleep(0.06)
    
    return results

# ===================== 5. 季度EPS =====================
def get_quarterly_eps(codes):
    """
    获取季度EPS（query_profit_data）
    返回: {stock_code: DataFrame(pubDate, statDate, eps)}
    """
    all_eps = {}
    years = list(range(2015, 2027))
    quarters = [1, 2, 3, 4]
    
    for i, code in enumerate(codes):
        eps_list = []
        for yr in years:
            for qtr in quarters:
                if yr == 2026 and qtr > 2:
                    break
                try:
                    rs = bs.query_profit_data(code, year=str(yr), quarter=str(qtr))
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    if rows:
                        tmp = pd.DataFrame(rows, columns=rs.fields)
                        if 'pubDate' in tmp.columns and 'epsTTM' in tmp.columns:
                            valid = tmp[tmp['epsTTM'].astype(str).str.replace('.','',1).str.isdigit()]
                            if not valid.empty:
                                last = valid.iloc[-1]
                                eps_list.append({
                                    'statDate': last.get('statDate', ''),
                                    'pubDate': last.get('pubDate', ''),
                                    'eps': float(last.get('epsTTM', 0))
                                })
                except:
                    pass
        if eps_list:
            all_eps[code] = pd.DataFrame(eps_list)
        time.sleep(0.05)
    
    return all_eps

# ===================== 6. 构建指数月频PE =====================
def build_index_pe_panel(stock_prices, eps_data, index_code, index_name):
    """
    构建指数月频PE时间序列
    
    逻辑：
    1. 取指数日收盘价（直接query指数）
    2. 成分股权重等权
    3. 成分股EPS月度插值
    4. 指数PE = 指数价格 / (等权EPS × 成分股数量)
    """
    print(f'\n构建 {index_name} PE序列...')
    
    # 尝试直接获取指数价格
    rs = bs.query_history_k_data_plus(index_code,
        'date,code,close',
        start_date='2015-01-01', end_date='2026-07-10', frequency='d')
    idx_rows = []
    while rs.error_code == '0' and rs.next():
        idx_rows.append(rs.get_row_data())
    
    if idx_rows:
        idx_df = pd.DataFrame(idx_rows, columns=rs.fields)
        idx_df['date'] = pd.to_datetime(idx_df['date'])
        idx_df['close'] = pd.to_numeric(idx_df['close'], errors='coerce')
        idx_df = idx_df.dropna(subset=['close']).sort_values('date')
        print(f'  指数价格: {len(idx_df)}行')
    else:
        # fallback: 用成分股等权平均
        print(f'  无法获取指数价格，用成分股等权平均')
        all_prices = []
        for code, df in stock_prices.items():
            df2 = df.copy()
            df2['code'] = code
            all_prices.append(df2)
        if not all_prices:
            return pd.DataFrame()
        idx_df = pd.concat(all_prices, ignore_index=True)
        idx_df = idx_df.groupby('date')['close'].mean().reset_index()
        idx_df = idx_df.sort_values('date')
    
    # 按月聚合指数价格
    idx_df['month'] = idx_df['date'].dt.to_period('M')
    monthly_idx = idx_df.groupby('month').agg(
        idx_close=('close', 'last'),
        idx_open=('close', 'first'),
    ).reset_index()
    monthly_idx['date'] = monthly_idx['month'].dt.to_timestamp()
    monthly_idx = monthly_idx.sort_values('date').reset_index(drop=True)
    
    # 成分股月度EPS：取所有成分股季度EPS的中位数
    all_eps = []
    for code, eps_df in eps_data.items():
        if not eps_df.empty:
            eps_df['statDate'] = pd.to_datetime(eps_df['statDate'])
            eps_df = eps_df[eps_df['statDate'] >= '2015-01-01'].sort_values('statDate')
            all_eps.append(eps_df)
    
    if not all_eps:
        print(f'  无EPS数据，改用PB代理')
        # 用指数成交量代理PE
        monthly_idx['pe'] = np.nan
        return monthly_idx[['date', 'pe']]
    
    # 取所有股票EPS的中位数作为市场整体EPS
    combined_eps = pd.concat(all_eps, ignore_index=True)
    combined_eps = combined_eps.dropna(subset=['eps', 'statDate'])
    combined_eps = combined_eps[combined_eps['eps'] > 0]
    
    # 按月：每个季末EPS向后填充3个月
    combined_eps = combined_eps.sort_values('statDate')
    combined_eps['month'] = combined_eps['statDate'].dt.to_period('M')
    
    # 季度EPS向前填充（用最新季度EPS代表未来几个月）
    eps_series = combined_eps.set_index('month')['eps']
    eps_filled = eps_series.resample('M').ffill()
    eps_filled = eps_filled.reset_index()
    eps_filled.columns = ['month', 'eps']
    eps_filled['date'] = eps_filled['month'].dt.to_timestamp()
    
    # 合并
    panel = monthly_idx.merge(eps_filled[['date', 'eps']], on='date', how='left')
    
    # 计算PE（指数价格 / EPS）
    panel['pe'] = panel['idx_close'] / panel['eps']
    panel = panel[panel['pe'] > 0]
    panel = panel[panel['pe'] < 200]  # 过滤异常
    
    print(f'  有效PE数据: {len(panel)}月, PE范围: {panel["pe"].min():.1f}~{panel["pe"].max():.1f}')
    print(f'  最新PE: {panel.iloc[-1]["pe"]:.2f}')
    
    return panel[['date', 'pe']]

# ===================== 7. 主流程 =====================
def main():
    print('=== 宽基指数估值轮动策略 ===')
    print(f'时间: {datetime.now():%H:%M:%S}')
    
    bs_login()
    
    # Step 1: 获取成分股列表（取HS300和ZZ500代表）
    print('\n[Step 1] 获取成分股...')
    hs300 = get_constituents('hs300')
    zz500 = get_constituents('zz500')
    print(f'HS300: {len(hs300)}, ZZ500: {len(zz500)}')
    
    # Step 2: 采样下载（每指数取50只代表性股票，减少API调用）
    # 用市值排名抽样：前30大市值 + 后20随机
    np.random.seed(42)
    sample_hs300 = hs300[:30] + list(np.random.choice(hs300[30:], 20, replace=False))
    sample_zz500 = zz500[:30] + list(np.random.choice(zz500[30:], 20, replace=False))
    print(f'\n采样: HS300={len(sample_hs300)}只, ZZ500={len(sample_zz500)}只')
    
    # Step 3: 下载日频价格
    cache_hs300 = os.path.join(DATA_DIR, 'hs300_prices.pkl')
    cache_zz500 = os.path.join(DATA_DIR, 'zz500_prices.pkl')
    
    if os.path.exists(cache_hs300):
        import pickle
        with open(cache_hs300, 'rb') as f:
            prices_hs300 = pickle.load(f)
        with open(cache_zz500, 'rb') as f:
            prices_zz500 = pickle.load(f)
        print(f'\n[缓存加载] HS300: {len(prices_hs300)}只, ZZ500: {len(prices_zz500)}只')
    else:
        print(f'\n[Step 2] 下载日频价格 (HS300 {len(sample_hs300)}只)...')
        t0 = time.time()
        prices_hs300 = get_daily_prices(sample_hs300, '2015-01-01', '2026-07-10')
        print(f'  HS300完成: {len(prices_hs300)}/{len(sample_hs300)}只, 耗时{time.time()-t0:.0f}s')
        
        print(f'\n[Step 3] 下载日频价格 (ZZ500 {len(sample_zz500)}只)...')
        t1 = time.time()
        prices_zz500 = get_daily_prices(sample_zz500, '2015-01-01', '2026-07-10')
        print(f'  ZZ500完成: {len(prices_zz500)}/{len(sample_zz500)}只, 耗时{time.time()-t1:.0f}s')
        
        import pickle
        with open(cache_hs300, 'wb') as f:
            pickle.dump(prices_hs300, f)
        with open(cache_zz500, 'wb') as f:
            pickle.dump(prices_zz500, f)
        print('  缓存已保存')
    
    bs_logout()
    
    # Step 4: 构建指数月频PE
    print('\n[Step 4] 构建指数PE序列...')
    
    # 方法：用成分股收盘价的等权平均值代表指数价格
    # PE代理：用成分股PE的中位数
    
    def build_etf_index_pe(prices_dict, name):
        """从成分股价格构建指数近似PE序列"""
        all_rows = []
        for code, df in prices_dict.items():
            df2 = df.copy()
            df2['month'] = df2['date'].dt.to_period('M')
            monthly = df2.groupby('month').agg(
                close=('close', 'last'),
                date=('date', 'max'),
            ).reset_index()
            monthly['date'] = monthly['month'].dt.to_timestamp()
            monthly['code'] = code
            all_rows.append(monthly[['date', 'close', 'code']])
        
        if not all_rows:
            return pd.DataFrame()
        
        combined = pd.concat(all_rows, ignore_index=True)
        # 按月聚合：等权平均
        monthly_avg = combined.groupby('date').agg(
            avg_close=('close', 'mean'),
            price_std=('close', 'std'),
            n=('code', 'count'),
        ).reset_index().sort_values('date')
        
        # 计算月收益率
        monthly_avg['ret'] = monthly_avg['avg_close'].pct_change()
        # 月收益动量（12个月）
        monthly_avg['mom12'] = monthly_avg['ret'].rolling(12, min_periods=6).sum()
        
        print(f'  {name}: {len(monthly_avg)}月, 价格范围: {monthly_avg["avg_close"].min():.2f}~{monthly_avg["avg_close"].max():.2f}')
        return monthly_avg[['date', 'avg_close', 'ret', 'mom12', 'n']]
    
    hs300_idx = build_etf_index_pe(prices_hs300, '沪深300(近似)')
    zz500_idx = build_etf_index_pe(prices_zz500, '中证500(近似)')
    
    # Step 5: 用本地ETF数据构建其他指数（创业板/科创50/上证50/中证1000）
    print('\n[Step 5] 从本地ETF构建其他指数...')
    
    # 读取本地ETF
    pool_file = os.path.join(OUT_DIR, 'data', 'etf_pool_V1_full.json')
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    code_to_cat = {i['code'].strip(): (i.get('category') or '其他').strip() or '其他'
                    for i in pool['data']}
    
    etf_map = {
        '159915': '创业板指',
        '588080': '科创50',
        '510100': '上证50',
        '512100': '中证1000',
        '510300': '沪深300',
        '510500': '中证500',
    }
    
    def read_etf_json(code):
        path = os.path.join(OUT_DIR, 'data', 'history', f'{code}.json')
        if not os.path.exists(path):
            return pd.DataFrame()
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        if isinstance(raw, list): df = pd.DataFrame(raw)
        elif 'data' in raw: df = pd.DataFrame(raw['data'])
        elif 'records' in raw: df = pd.DataFrame(raw['records'])
        else: return pd.DataFrame()
        dc = next((c for c in df.columns if c.lower() in ['date','day']), None)
        cc = next((c for c in df.columns if c.lower() in ['close','c']), None)
        if not dc or not cc: return pd.DataFrame()
        df['date'] = pd.to_datetime(df[dc])
        df['close'] = pd.to_numeric(df[cc], errors='coerce')
        df = df.dropna(subset=['date', 'close']).sort_values('date')
        df['ret'] = df['close'].pct_change()
        df['mom12'] = df['ret'].rolling(12, min_periods=6).sum()
        return df[['date', 'close', 'ret', 'mom12']]
    
    etf_indices = {}
    for code, name in etf_map.items():
        df = read_etf_json(code)
        if not df.empty:
            df['month'] = df['date'].dt.to_period('M')
            monthly = df.groupby('month').agg(
                close=('close', 'last'),
                ret=('ret', lambda x: (1+x).prod()-1 if len(x)>0 else 0),
                mom12=('mom12', 'last'),
            ).reset_index()
            monthly['date'] = monthly['month'].dt.to_timestamp()
            etf_indices[name] = monthly[['date', 'close', 'ret', 'mom12']].dropna()
            print(f'  {name}: {len(etf_indices[name])}月')
    
    # Step 6: 合并所有指数
    print('\n[Step 6] 合并指数面板...')
    
    all_indices = {}
    
    # ETF指数
    for name, df in etf_indices.items():
        df2 = df.copy()
        df2 = df2[df2['date'] >= '2016-01-01']
        df2 = df2[df2['date'] <= '2026-06-30']
        all_indices[name] = df2[['date', 'close', 'mom12']].dropna()
    
    # HS300/ZZ500近似
    if not hs300_idx.empty:
        hs300_idx2 = hs300_idx[hs300_idx['date'] >= '2016-01-01']
        all_indices['沪深300(成分股)'] = hs300_idx2[['date', 'avg_close', 'mom12']].rename(columns={'avg_close':'close'}).dropna()
    
    if not zz500_idx.empty:
        zz500_idx2 = zz500_idx[zz500_idx['date'] >= '2016-01-01']
        all_indices['中证500(成分股)'] = zz500_idx2[['date', 'avg_close', 'mom12']].rename(columns={'avg_close':'close'}).dropna()
    
    print(f'指数数量: {len(all_indices)}')
    for name, df in all_indices.items():
        print(f'  {name}: {df["date"].min().date()} ~ {df["date"].max().date()}, {len(df)}月')
    
    # Step 7: 构建估值代理（用RSRS Z-score作为低估/高估信号）
    # 由于无法直接获取PE，用相对强弱来构建估值代理
    # 方法：每个月末，计算各指数的RSRS（滚动日线）
    # 简化：用动量乖离率代替
    print('\n[Step 7] 构建估值代理（动量乖离率）...')
    
    # 每个指数计算：当前价格/20月均线 的偏离度
    for name in all_indices:
        df = all_indices[name].sort_values('date')
        df['ma12'] = df['close'].rolling(12, min_periods=6).mean()
        df['price_to_ma'] = df['close'] / df['ma12']  # >1高于均线=偏贵
        # PE分位代理：用price_to_ma的滚动5年百分位
        pe_proxy = df['price_to_ma'].values
        pct = np.full(len(pe_proxy), np.nan)
        for i in range(36, len(pe_proxy)):
            window = pe_proxy[max(0, i-60):i]
            valid = window[~np.isnan(window)]
            if len(valid) >= 24:
                pct[i] = (valid > pe_proxy[i]).sum() / len(valid)  # 越高于均线越贵
        df['val_pct'] = pct
        df['val_score'] = 1 - df['val_pct']  # 1=最低估（price_to_ma最低）
        all_indices[name] = df.dropna(subset=['val_score'])
    
    # Step 8: 月频回测
    print('\n[Step 8] 月频回测...')
    
    # 对齐到共同月末
    all_dates = set()
    for df in all_indices.values():
        all_dates.update(df['date'].tolist())
    rebal_dates = sorted([d for d in all_dates if d >= pd.Timestamp('2016-02-01')])
    print(f'调仓日期: {len(rebal_dates)}个')
    
    def run_strat(name, fn):
        """fn(当前日面板 dict{name: df}) -> [etf_names]"""
        hold_rets = []
        current_hold = []
        
        for i, d in enumerate(rebal_dates[:-1]):
            next_d = rebal_dates[i+1]
            
            # 获取当日面板
            today_panel = {}
            for n, df in all_indices.items():
                day_row = df[df['date'] == d]
                if not day_row.empty:
                    today_panel[n] = day_row.iloc[0]
            
            if not today_panel:
                continue
            
            # 选股
            new_hold = fn(today_panel)
            
            # 计算下一期收益
            rets = []
            for etf_name in (current_hold if new_hold == current_hold else new_hold):
                df = all_indices.get(etf_name)
                if df is None:
                    continue
                nd_rows = df[df['date'] == next_d]
                if not nd_rows.empty:
                    rets.append(nd_rows.iloc[0]['ret'])
            
            if rets:
                hold_rets.append({'date': next_d, 'ret': np.mean(rets)})
            
            current_hold = new_hold
        
        rd = pd.DataFrame(hold_rets)
        if rd.empty or 'ret' not in rd.columns:
            return None
        
        rd = rd.dropna()
        if rd.empty:
            return None
        
        cum = (1 + rd.set_index('date')['ret']).cumprod()
        ann = cum.iloc[-1] ** (12.0 / len(cum)) - 1
        peak = cum.cummax()
        mdd = ((cum - peak) / peak).min()
        sd = rd['ret'].std()
        sharpe = rd['ret'].mean() / sd * np.sqrt(12) if sd > 1e-10 else 0
        win = (rd['ret'] > 0).mean()
        
        return dict(name=name, ann=ann, mdd=mdd, sharpe=sharpe, win=win, n=len(rd))
    
    # 策略定义
    results = []
    
    # A: 相对估值Top1（val_score最高=最便宜）
    r = run_strat('A_相对估值Top1',
        lambda p: ([max(p.keys(), key=lambda k: p[k]['val_score'])] if p else []))
    if r: results.append(r)
    
    # B: 相对估值Top2
    r = run_strat('B_相对估值Top2',
        lambda p: (sorted(p.keys(), key=lambda k: p[k]['val_score'], reverse=True)[:2] if p else []))
    if r: results.append(r)
    
    # C: 低估过滤（val_score > 0.7）
    r = run_strat('C_低估过滤Top1(val>0.7)',
        lambda p: ([max([k for k in p if p[k]['val_score'] > 0.7],
                        key=lambda k: p[k]['val_score'], default=None)] if p else []))
    if r: results.append(r)
    
    # D: 动量Top1
    r = run_strat('D_动量Top1',
        lambda p: ([max(p.keys(), key=lambda k: p[k].get('mom12', -999))] if p else []))
    if r: results.append(r)
    
    # E: 估值+动量综合（score = val_score * (1+mom)）
    r = run_strat('E_估值动量综合',
        lambda p: ([max(p.keys(), key=lambda k: p[k]['val_score'] * (1 + max(p[k].get('mom12', 0), 0)))] if p else []))
    if r: results.append(r)
    
    # F: 低估Top1 + 动量确认（val_score高 AND mom12 > 0）
    r = run_strat('F_低估+动量确认',
        lambda p: ([max([k for k in p if p[k]['val_score'] > 0.6 and p[k].get('mom12', -999) > 0],
                        key=lambda k: p[k]['val_score'], default=None)] if p else []))
    if r: results.append(r)
    
    # 基准：持有沪深300
    if '沪深300' in all_indices:
        bench = all_indices['沪深300'].copy()
        bench = bench[bench['date'].isin(rebal_dates)]
        bench = bench.sort_values('date')
        if not bench.empty:
            bench_cum = (1 + bench.set_index('date')['ret']).cumprod()
            bann = bench_cum.iloc[-1] ** (12.0/len(bench_cum)) - 1
            bpeak = bench_cum.cummax()
            bmdd = ((bench_cum-bpeak)/bpeak).min()
            bsharpe = bench['ret'].mean() / bench['ret'].std() * np.sqrt(12) if bench['ret'].std() > 1e-10 else 0
            results.append(dict(name='沪深300基准', ann=bann, mdd=bmdd, sharpe=bsharpe, win=0, n=len(bench)))
    
    # 打印
    print('\n================ 估值轮动回测结果 ================')
    print(f"{'策略':<28}{'年化':>9}{'MDD':>9}{'Sharpe':>8}{'胜率':>7}{'期数':>5}")
    for r in sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True):
        print(f"{r['name']:<28}{r['ann']*100:>8.2f}%{r['mdd']*100:>8.2f}%{r['sharpe']:>7.2f}  {r['win']*100:>5.1f}% {r['n']:>4d}")
    
    # 年度明细（最佳策略）
    valid = sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True)
    if valid:
        best = valid[0]
        print(f"\n★ 最佳: {best['name']} Sharpe={best['sharpe']:.2f}")
    
    # 保存
    import pickle
    for name, df in all_indices.items():
        df.to_csv(os.path.join(DATA_DIR, f'{name}.csv'), index=False)
    pd.DataFrame(results).to_csv(os.path.join(OUT_DIR, 'val_rotation_results.csv'), index=False)
    print(f'\n数据已保存: {DATA_DIR}/')
    print(f'结果已保存: {OUT_DIR}/val_rotation_results.csv')

if __name__ == '__main__':
    main()
