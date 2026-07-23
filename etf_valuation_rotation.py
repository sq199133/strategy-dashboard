# -*- coding: utf-8 -*-
"""
ETF估值轮动策略 — BaoStock数据驱动
策略A: 纯动量TOP1（12天动量 + ATR>0.90）
策略B: 低估值过滤（只选估值得分<0.4的板块中的动量最强）
策略C: 估值加权（动量分数×(1-估值分位)，让低估值板块得更高分）
策略D: 估值分位单独因子（选估值最低的板块，不看动量）
对比基准: 等权宽基
"""
import os
import sys
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# ===================== 路径配置 =====================
# 优先从BaoStock数据目录读取；若无数据则尝试AkShare数据目录
DATA_DIR_BS = r"D:\QClaw_Trading\data\baostock_etf"
DATA_DIR_AK = r"D:\QClaw_Trading\data\akshare_etf"
POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
OUTPUT_DIR = r"D:\QClaw_Trading"

np.random.seed(42)


# ===================== 数据加载 =====================
def load_all_etf_data(start_date='2019-01-01', end_date='2026-07-10'):
    """加载所有CSV文件，合并为一个DataFrame
    优先从BaoStock目录读取；若无可用数据则尝试AkShare目录
    """
    # 尝试BaoStock目录
    csv_files = sorted(Path(DATA_DIR_BS).glob("*.csv"))
    data_source = 'BaoStock'
    if not csv_files:
        csv_files = sorted(Path(DATA_DIR_AK).glob("*.csv"))
        data_source = 'AkShare'
    
    print(f"[{data_source}] 发现 {len(csv_files)} 个CSV文件")
    
    all_data = []
    for f in csv_files:
        fname = f.stem  # 20240101 或 pe_pb_snapshot
        # 跳过非日期文件
        if not fname[:4].isdigit():
            continue
        file_date = f"{fname[:4]}-{fname[4:6]}-{fname[6:8]}"
        if file_date < start_date or file_date > end_date:
            continue
        try:
            df = pd.read_csv(f, encoding='utf-8-sig')
            df['date'] = pd.to_datetime(df['date'])
            
            # 标准化列名（AkShare vs BaoStock）
            if '代码' in df.columns:
                df = df.rename(columns={'代码': 'code', '名称': 'name'})
            
            # 统一需要的列
            required = ['date', 'code', 'close', 'volume', 'amount', 'peTTM', 'pbMRQ']
            for col in ['close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            for col in ['peTTM', 'pbMRQ']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            all_data.append(df)
        except Exception as e:
            print(f"  读取 {f.name} 失败: {e}")
    
    if not all_data:
        print("警告: 未加载到任何数据！")
        return pd.DataFrame()
    
    df = pd.concat(all_data, ignore_index=True)
    df = df.sort_values(['date', 'code']).reset_index(drop=True)
    print(f"合并数据: {len(df)} 行, 日期范围 {df['date'].min()} ~ {df['date'].max()}")
    return df


# ===================== 板块指数构建 =====================
def build_sector_indices(raw_df, pool_file):
    """按板块聚合ETF，构建板块价格指数（等权）"""
    # Demo模式：数据已有sector列
    if 'sector' in raw_df.columns and 'close' in raw_df.columns:
        sector_daily = raw_df.copy()
        sector_daily['date'] = pd.to_datetime(sector_daily['date'])
        
        # 按日期+板块聚合
        agg_df = sector_daily.groupby(['date', 'sector']).agg(
            sector_close=('close', 'mean'),
            volume_sum=('volume', 'sum'),
            peTTM_mean=('peTTM_mean', 'mean'),
            pbMRQ_mean=('pbMRQ_mean', 'mean'),
            n_etfs=('n_etfs', 'first'),  # demo模式下每个板块固定ETF数量
            atr=('atr', 'mean'),
        ).reset_index()
        
        agg_df = agg_df.sort_values(['sector', 'date'])
        agg_df['return'] = agg_df.groupby('sector')['sector_close'].pct_change()
        print(f"[Demo模式] 板块指数构建完成: {agg_df['sector'].nunique()} 个板块, "
              f"{agg_df['date'].nunique()} 个交易日")
        return agg_df, raw_df
    
    # 真实数据模式
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    code_to_cat = {}
    for item in pool['data']:
        code = item['code'].strip()
        cat = (item.get('category') or '其他').strip()
        if not cat:
            cat = '其他'
        code_to_cat[code] = cat
    
    def normalize_code(c):
        c = str(c).strip()
        if '.' in c:
            return c
        if len(c) == 6:
            if c.startswith(('0','3')):
                return f'sz.{c}'
            else:
                return f'sh.{c}'
        return c
    
    raw_df = raw_df.copy()
    raw_df['code_norm'] = raw_df['code'].apply(normalize_code)
    raw_df['category'] = raw_df['code_norm'].map(code_to_cat).fillna('其他')
    
    raw_df['peTTM'] = pd.to_numeric(raw_df['peTTM'], errors='coerce')
    raw_df['pbMRQ'] = pd.to_numeric(raw_df['pbMRQ'], errors='coerce')
    
    sector_daily = raw_df.groupby(['date', 'category']).agg(
        sector_close=('close', 'mean'),
        volume_sum=('volume', 'sum'),
        peTTM_mean=('peTTM', 'mean'),
        pbMRQ_mean=('pbMRQ', 'mean'),
        n_etfs=('code', 'count'),
    ).reset_index()
    
    sector_daily = sector_daily.rename(columns={'category': 'sector'})
    sector_daily = sector_daily.sort_values(['sector', 'date'])
    sector_daily['return'] = sector_daily.groupby('sector')['sector_close'].pct_change()
    
    raw_df2 = raw_df.copy()
    raw_df2['tr'] = raw_df2['high'] - raw_df2['low']
    sector_atr = raw_df2.groupby(['date', 'category'])['tr'].mean().reset_index()
    sector_atr.columns = ['date', 'sector', 'atr']
    
    sector_daily = sector_daily.merge(sector_atr, on=['date', 'sector'], how='left')
    
    print(f"板块指数构建完成: {sector_daily['sector'].nunique()} 个板块, "
          f"{sector_daily['date'].nunique()} 个交易日")
    return sector_daily, raw_df


# ===================== 估值分位计算 =====================
def calc_valuation_percentile(sector_df, lookback_days=252*5):
    """
    对每个板块，计算PE和PB分位（当日在近5年中的百分位）
    使用滚动窗口，非参数百分位
    """
    sector_df = sector_df.copy()
    
    # 确保date是datetime64，统一格式
    sector_df['date'] = pd.to_datetime(sector_df['date'])
    sector_df = sector_df.sort_values(['sector', 'date']).reset_index(drop=True)
    
    # PE/PB均值（取有效值）
    sector_df['peTTM_mean'] = sector_df['peTTM_mean'].replace(0, np.nan)
    sector_df['pbMRQ_mean'] = sector_df['pbMRQ_mean'].replace(0, np.nan)
    
    # 预分配结果列
    sector_df['pe_pct'] = np.nan
    sector_df['pb_pct'] = np.nan
    
    sectors = sector_df['sector'].unique()
    window = lookback_days // 5  # 近似5年窗口（每5天一个数据点）
    
    for sec in sectors:
        mask = sector_df['sector'] == sec
        sec_idx = sector_df[mask].sort_values('date').index
        
        pe_vals = sector_df.loc[sec_idx, 'peTTM_mean'].values.astype(float)
        pb_vals = sector_df.loc[sec_idx, 'pbMRQ_mean'].values.astype(float)
        
        for i in range(60, len(pe_vals)):
            start_i = max(0, i - window)
            
            pe_hist = pe_vals[start_i:i]
            pb_hist = pb_vals[start_i:i]
            
            pe_valid = pe_hist[~np.isnan(pe_hist)]
            pb_valid = pb_hist[~np.isnan(pb_hist)]
            
            cur_pe = pe_vals[i]
            cur_pb = pb_vals[i]
            
            if len(pe_valid) > 20 and not np.isnan(cur_pe):
                sector_df.loc[sec_idx[i], 'pe_pct'] = (pe_valid <= cur_pe).sum() / len(pe_valid)
            if len(pb_valid) > 20 and not np.isnan(cur_pb):
                sector_df.loc[sec_idx[i], 'pb_pct'] = (pb_valid <= cur_pb).sum() / len(pb_valid)
    
    # 估值得分
    sector_df['valuation_score'] = (sector_df['pe_pct'] + sector_df['pb_pct']) / 2
    sector_df['valuation_score'] = sector_df['valuation_score'].clip(0, 1)
    
    print("估值分位计算完成")
    return sector_df


# ===================== 动量 & ATR因子 =====================
def calc_momentum_atr(sector_df, momentum_days=12):
    """计算各板块的动量和ATR百分位"""
    sector_df = sector_df.copy()
    sector_df = sector_df.sort_values(['sector', 'date'])
    
    # 12天累计收益（动量）
    sector_df['momentum'] = sector_df.groupby('sector')['return'].transform(
        lambda x: x.rolling(momentum_days, min_periods=5).sum()
    )
    
    # ATR百分位（当日ATR在近60天的百分位）
    sector_df['atr_pct'] = sector_df.groupby('sector')['atr'].transform(
        lambda x: x.rolling(60, min_periods=20).apply(
            lambda arr: float(pd.Series(arr).rank(pct=True).iloc[-1]) if not np.isnan(arr[-1]) else np.nan,
            raw=True
        )
    )
    
    return sector_df


# ===================== 回测引擎 =====================
def backtest_strategy(sector_df, strategy_fn, name, initial_capital=1000000, 
                       rebalance_days=5):
    """
    通用回测函数
    strategy_fn(sector_snapshot) -> selected_sector (str or None)
    sector_snapshot: 当日各板块的因子DataFrame
    """
    # 按月调仓（每5个交易日，即约每月）
    sector_df = sector_df.sort_values('date').copy()
    
    # 标记调仓日
    dates = sector_df['date'].unique()
    rebalance_idx = list(range(0, len(dates), rebalance_days))
    
    capital = initial_capital
    position = None  # 当前持仓板块
    shares = 0
    
    history = []
    cur_capital = capital
    
    for i, date in enumerate(dates):
        snap = sector_df[sector_df['date'] == date].copy()
        if len(snap) == 0:
            continue
        
        # 计算当日组合净值
        if position and position in snap['sector'].values:
            ret_today = snap.loc[snap['sector'] == position, 'return'].values[0]
            cur_capital = cur_capital * (1 + ret_today)
        
        # 调仓判断
        if i in rebalance_idx:
            selected = strategy_fn(snap)
            position = selected
            if selected and selected in snap['sector'].values:
                ret_today = snap.loc[snap['sector'] == selected, 'return'].values[0]
                # 实际在调仓日以当日收益结算
                cur_capital = cur_capital * (1 + ret_today)
        
        history.append({
            'date': date,
            'capital': cur_capital,
            'position': position
        })
    
    result = pd.DataFrame(history)
    result['return_pct'] = result['capital'].pct_change().fillna(0)
    
    # 统计指标
    total_return = (result['capital'].iloc[-1] / initial_capital - 1) * 100
    annual_days = 252
    annual_return = ((1 + result['return_pct'].mean()) ** annual_days - 1) * 100
    
    # 年化（精确）
    n_years = (result['date'].iloc[-1] - result['date'].iloc[0]).days / 365.25
    if n_years > 0:
        cagr = ((result['capital'].iloc[-1] / initial_capital) ** (1/n_years) - 1) * 100
    else:
        cagr = 0
    
    # 最大回撤
    peak = result['capital'].cummax()
    drawdown = (result['capital'] - peak) / peak * 100
    max_drawdown = drawdown.min()
    
    # Sharpe
    daily_rf = 0.03 / 252
    excess = result['return_pct'] - daily_rf
    sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0
    
    # Calmar
    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0
    
    print(f"\n{'='*50}")
    print(f"策略: {name}")
    print(f"  总收益率: {total_return:.2f}%")
    print(f"  年化收益: {cagr:.2f}%")
    print(f"  最大回撤: {max_drawdown:.2f}%")
    print(f"  Sharpe: {sharpe:.3f}")
    print(f"  Calmar: {calmar:.3f}")
    print(f"  期末净值: {result['capital'].iloc[-1]:,.2f}")
    print(f"{'='*50}")
    
    return {
        'name': name,
        'total_return': total_return,
        'cagr': cagr,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'calmar': calmar,
        'final_capital': result['capital'].iloc[-1],
        'history': result
    }


# ===================== 四大策略 =====================
def strategy_A_pure_momentum(snap):
    """策略A: 纯动量TOP1（12天动量 + ATR>0.90，即波动足够大）"""
    valid = snap.dropna(subset=['momentum', 'atr_pct']).copy()
    if valid.empty:
        return None
    
    # ATR过滤：排除波动太低的板块（动量无效）
    valid = valid[valid['atr_pct'] >= 0.10]  # ATR在前10%以内
    
    if valid.empty:
        valid = snap.dropna(subset=['momentum'])
    
    if valid.empty:
        return None
    
    # 选动量最强的
    best = valid.loc[valid['momentum'].idxmax()]
    return best['sector']


def strategy_B_value_filter(snap, threshold=0.4):
    """策略B: 低估值过滤 + 动量最强（只选估值得分<threshold的板块中的动量最强）"""
    valid = snap.dropna(subset=['momentum', 'valuation_score']).copy()
    if valid.empty:
        return None
    
    # 低估值过滤
    low_val = valid[valid['valuation_score'] < threshold]
    
    if low_val.empty:
        # 如果没有低估值板块，回到全市场动量
        low_val = valid
    
    if low_val.empty:
        return None
    
    best = low_val.loc[low_val['momentum'].idxmax()]
    return best['sector']


def strategy_C_value_weighted(snap):
    """策略C: 估值加权（动量分数 × (1 - 估值分位)，让低估值板块得更高分）"""
    valid = snap.dropna(subset=['momentum', 'valuation_score']).copy()
    if valid.empty:
        return None
    
    # 动量分数标准化（0~1）
    mom_min = valid['momentum'].min()
    mom_max = valid['momentum'].max()
    if mom_max > mom_min:
        valid['mom_score'] = (valid['momentum'] - mom_min) / (mom_max - mom_min)
    else:
        valid['mom_score'] = 0.5
    
    # 估值加权分 = 动量分数 × (1 - 估值得分)
    valid['combined_score'] = valid['mom_score'] * (1 - valid['valuation_score'])
    
    best = valid.loc[valid['combined_score'].idxmax()]
    return best['sector']


def strategy_D_pure_valuation(snap):
    """策略D: 纯估值（选估值得分最低的板块，不看动量）"""
    valid = snap.dropna(subset=['valuation_score']).copy()
    if valid.empty:
        return None
    
    best = valid.loc[valid['valuation_score'].idxmin()]
    return best['sector']


def benchmark_equal_weight(sector_df, sectors=['宽基A股', '红利策略', '商品/周期/资源'], 
                           initial_capital=1000000, rebalance_days=5):
    """等权宽基基准：几个主要宽基板块等权配置"""
    dates = sorted(sector_df['date'].unique())
    rebalance_idx = list(range(0, len(dates), rebalance_days))
    
    capital = initial_capital
    positions = {}  # sector -> weight
    history = []
    
    for i, date in enumerate(dates):
        snap = sector_df[sector_df['date'] == date].copy()
        
        # 调仓
        if i in rebalance_idx:
            # 等权分配到几个基准板块
            weights = {}
            for sec in sectors:
                if sec in snap['sector'].values:
                    weights[sec] = 1.0 / len(sectors)
        
        # 累计收益
        daily_ret = 0
        for sec, w in weights.items():
            if sec in snap['sector'].values:
                r = snap.loc[snap['sector'] == sec, 'return'].values[0]
                daily_ret += w * r
        
        capital = capital * (1 + daily_ret)
        history.append({'date': date, 'capital': capital, 'position': 'benchmark'})
    
    result = pd.DataFrame(history)
    result['return_pct'] = result['capital'].pct_change().fillna(0)
    
    total_return = (result['capital'].iloc[-1] / initial_capital - 1) * 100
    n_years = (result['date'].iloc[-1] - result['date'].iloc[0]).days / 365.25
    cagr = ((result['capital'].iloc[-1] / initial_capital) ** (1/n_years) - 1) * 100 if n_years > 0 else 0
    
    peak = result['capital'].cummax()
    drawdown = (result['capital'] - peak) / peak * 100
    max_drawdown = drawdown.min()
    
    daily_rf = 0.03 / 252
    excess = result['return_pct'] - daily_rf
    sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0
    
    print(f"\n{'='*50}")
    print(f"基准: 等权宽基")
    print(f"  总收益率: {total_return:.2f}%")
    print(f"  年化收益: {cagr:.2f}%")
    print(f"  最大回撤: {max_drawdown:.2f}%")
    print(f"  Sharpe: {sharpe:.3f}")
    print(f"  期末净值: {result['capital'].iloc[-1]:,.2f}")
    print(f"{'='*50}")
    
    return {
        'name': 'Benchmark(等权宽基)',
        'total_return': total_return,
        'cagr': cagr,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'final_capital': result['capital'].iloc[-1],
        'history': result
    }


# ===================== 主程序 =====================
def main():
    print("=" * 60)
    print("ETF估值轮动策略 — BaoStock数据驱动")
    print("=" * 60)
    
    # Step 1: 加载数据
    print("\n[Step 1] 加载BaoStock ETF数据...")
    raw_df = load_all_etf_data(start_date='2019-01-01', end_date='2026-07-10')
    
    if raw_df.empty:
        print("错误: 无法加载数据！请先运行下载脚本")
        # 尝试用模拟数据演示
        print("使用模拟数据演示...")
        raw_df = generate_demo_data()
    
    # Step 2: 构建板块指数
    print("\n[Step 2] 构建板块价格指数...")
    sector_df, _ = build_sector_indices(raw_df, POOL_FILE)
    
    # Step 3: 估值分位计算
    print("\n[Step 3] 计算估值分位 (PE/PB百分位，近5年窗口)...")
    sector_df = calc_valuation_percentile(sector_df)
    
    # Step 4: 动量 & ATR
    print("\n[Step 4] 计算动量 & ATR因子...")
    sector_df = calc_momentum_atr(sector_df, momentum_days=12)
    
    # 过滤回测期间（2020-2026，且有足够历史）
    sector_df['date'] = pd.to_datetime(sector_df['date']).dt.normalize()
    
    # 字符串比较（避免datetime64不同resolution的整数表示问题）
    date_str = sector_df['date'].dt.strftime('%Y-%m-%d')
    mask = (date_str >= '2020-01-01') & (date_str <= '2026-07-10')
    bt_df = sector_df.loc[mask].copy()
    
    if bt_df.empty:
        print("警告: 回测区间无数据！")
        return {}, sector_df
    
    # 过滤：必须有足够多板块覆盖（至少5个板块有数据）
    sector_count = bt_df.groupby('date')['sector'].count()
    valid_dates = sector_count[sector_count >= 5].index
    if len(valid_dates) == 0:
        print("警告: 无有效交易日！")
        return {}, sector_df
    bt_df = bt_df[bt_df['date'].isin(valid_dates)]
    
    min_date = bt_df['date'].min()
    max_date = bt_df['date'].max()
    print(f"\n回测区间: {getattr(min_date, 'date', min_date)()} ~ {getattr(max_date, 'date', max_date)()}")
    print(f"有效交易日: {bt_df['date'].nunique()} 天")
    print(f"板块数量: {bt_df['sector'].nunique()}")
    
    # Step 5: 回测
    print("\n[Step 5] 开始回测...")
    
    results = {}
    
    # 基准
    results['Benchmark'] = benchmark_equal_weight(bt_df, rebalance_days=5)
    
    # 策略A
    results['策略A_纯动量'] = backtest_strategy(
        bt_df, strategy_A_pure_momentum, 
        '策略A: 纯动量TOP1(12天动量+ATR过滤)',
        rebalance_days=5
    )
    
    # 策略B
    results['策略B_低估值过滤'] = backtest_strategy(
        bt_df, lambda s: strategy_B_value_filter(s, threshold=0.4),
        '策略B: 低估值过滤(得分<0.4)+动量最强',
        rebalance_days=5
    )
    
    # 策略C
    results['策略C_估值加权'] = backtest_strategy(
        bt_df, strategy_C_value_weighted,
        '策略C: 估值加权(动量×(1-估值分位))',
        rebalance_days=5
    )
    
    # 策略D
    results['策略D_纯估值'] = backtest_strategy(
        bt_df, strategy_D_pure_valuation,
        '策略D: 纯估值(选估值得分最低)',
        rebalance_days=5
    )
    
    # 汇总对比表
    print("\n" + "=" * 70)
    print("策略对比汇总 (2020-2026)")
    print("=" * 70)
    summary = []
    for name, r in results.items():
        summary.append({
            '策略': r['name'],
            '总收益率': f"{r['total_return']:.1f}%",
            '年化收益': f"{r['cagr']:.1f}%",
            '最大回撤': f"{r['max_drawdown']:.1f}%",
            'Sharpe': f"{r['sharpe']:.3f}",
            'Calmar': f"{r.get('calmar', 0):.3f}",
            '期末净值': f"{r['final_capital']:,.0f}"
        })
    
    summary_df = pd.DataFrame(summary)
    print(summary_df.to_string(index=False))
    
    # 保存结果
    summary_df.to_csv(os.path.join(OUTPUT_DIR, 'strategy_summary.csv'), 
                      index=False, encoding='utf-8-sig')
    
    # 保存净值曲线
    nav_data = {}
    for name, r in results.items():
        hist = r['history'][['date', 'capital']].copy()
        hist.columns = ['date', r['name']]
        nav_data[r['name']] = hist.set_index('date')
    
    nav_df = pd.concat(nav_data.values(), axis=1)
    nav_df.index = pd.to_datetime(nav_df.index)
    nav_df.to_csv(os.path.join(OUTPUT_DIR, 'strategy_nav.csv'), 
                  encoding='utf-8-sig')
    print(f"\n净值曲线已保存到: {OUTPUT_DIR}\\strategy_nav.csv")
    print(f"汇总表已保存到: {OUTPUT_DIR}\\strategy_summary.csv")
    
    return results, sector_df


def generate_demo_data():
    """当无真实数据时，生成演示用的模拟数据"""
    print("[DEMO模式] 生成模拟数据进行演示...")
    from datetime import datetime, timedelta
    
    dates = pd.date_range('2019-01-01', '2026-07-10', freq='5D')
    sectors = ['宽基A股', '红利策略', '商品/周期/资源', '金融', '消费', 
               '医药生物', '科技/TMT/AI', '制造/基建/公用', '芯片半导体', '港股/中概']
    
    np.random.seed(42)
    data = []
    prev_prices = {s: 1.0 for s in sectors}
    
    for date in dates:
        for sector in sectors:
            prev = prev_prices[sector]
            noise = np.random.normal(0, 0.015)
            # 赋予不同板块不同特征
            if sector == '科技/TMT/AI':
                trend = 0.0006
            elif sector == '红利策略':
                trend = 0.0002
            elif sector == '商品/周期/资源':
                trend = 0.0003
            elif sector == '芯片半导体':
                trend = 0.0005
            else:
                trend = 0.00025
            
            ret = trend + noise
            close = prev * (1 + ret)
            high = close * (1 + abs(np.random.normal(0, 0.005)))
            low = close * (1 - abs(np.random.normal(0, 0.005)))
            prev_prices[sector] = close
            
            pe = np.random.uniform(8, 40)
            pb = np.random.uniform(0.8, 5.0)
            atr = abs(noise) + 0.005
            
            data.append({
                'date': date,
                'code': f'demo.{sector}',
                'sector': sector,
                'close': close,
                'open': close * (1 - abs(np.random.normal(0, 0.002))),
                'high': high,
                'low': low,
                'preclose': prev,
                'volume': np.random.uniform(1000000, 10000000),
                'amount': close * np.random.uniform(1000000, 10000000),
                'return': ret,
                'atr': atr,
                'peTTM_mean': pe,
                'pbMRQ_mean': pb,
                'n_etfs': 5,
                'peTTM': pe,
                'pbMRQ': pb,
            })
    
    return pd.DataFrame(data)


if __name__ == '__main__':
    results, sector_df = main()
