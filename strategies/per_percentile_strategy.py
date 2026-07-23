# -*- coding: utf-8 -*-
"""
PER分位择时策略框架
=====================
策略思路：
- 基于ETF/指数的PER历史分位进行择时
- 低分位（如<20%）低估，加仓信号
- 高分位（如>80%）高估，减仓信号

数据需求：
- ETF历史价格数据（已有）
- 指数/ETF的PER估值数据（需要获取）

作者: 策略测算
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置模块
# ============================================

class StrategyConfig:
    """策略配置"""
    
    # 数据路径
    DATA_DIR = "D:/QClaw_Trading/data"
    ETF_POOL_FILE = "etf_pool_V1_full.json"
    HISTORY_DIR = "history"
    HISTORY_LONG_DIR = "history_long"
    INDEX_HISTORY_DIR = "index_history"
    
    # PER分位阈值
    PER_LOW_THRESHOLD = 20      # 低分位阈值（百分位）
    PER_HIGH_THRESHOLD = 80     # 高分位阈值（百分位）
    PER_EXTREME_LOW = 10       # 极低分位（强买入信号）
    PER_EXTREME_HIGH = 90     # 极高分位（强卖出信号）
    
    # 滚动窗口（用于计算分位）
    PERCENTILE_WINDOW = 252    # 默认1年（252个交易日）
    PERCENTILE_WINDOW_LONG = 756   # 3年窗口
    
    # 交易参数
    TRANSACTION_COST = 0.0003   # 交易成本（万分之三）
    SLIPPAGE = 0.0001           # 滑点（万分之一）
    MIN_TRADE_AMOUNT = 100     # 最小交易单位
    
    # 回测参数
    INITIAL_CAPITAL = 1000000   # 初始资金
    POSITION_SIZE = 0.3         # 单次调仓比例


# ============================================
# 数据获取模块
# ============================================

class DataLoader:
    """数据加载器"""
    
    def __init__(self, data_dir: str = StrategyConfig.DATA_DIR):
        self.data_dir = data_dir
        self.etf_pool = None
        self.price_cache = {}
        
    def load_etf_pool(self) -> Dict:
        """加载ETF标的池"""
        filepath = os.path.join(self.data_dir, StrategyConfig.ETF_POOL_FILE)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.etf_pool = data
        return data
    
    def load_etf_history(self, etf_code: str, use_long: bool = False) -> pd.DataFrame:
        """
        加载ETF历史数据
        
        Args:
            etf_code: ETF代码（如 '510300'）
            use_long: 是否使用长期历史数据
            
        Returns:
            DataFrame with columns: date, open, close, high, low, vol, amount, chg
        """
        # 构建文件名（添加前缀）
        if etf_code.startswith('6'):
            filename = f"sh{etf_code}.json"
        else:
            filename = f"sz{etf_code}.json"
        
        # 选择目录
        if use_long:
            dir_path = os.path.join(self.data_dir, StrategyConfig.HISTORY_LONG_DIR)
        else:
            dir_path = os.path.join(self.data_dir, StrategyConfig.HISTORY_DIR)
        
        filepath = os.path.join(dir_path, filename)
        
        if not os.path.exists(filepath):
            # 尝试另一种命名格式
            if etf_code.startswith('5'):
                filename = f"sh{etf_code}.json"
            elif etf_code.startswith('1'):
                filename = f"sz{etf_code}.json"
            filepath = os.path.join(dir_path, filename)
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 转换为DataFrame
        if 'records' in data:
            df = pd.DataFrame(data['records'])
        else:
            df = pd.DataFrame(data)
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
    
    def load_index_history(self, index_code: str) -> pd.DataFrame:
        """
        加载指数历史数据
        
        Args:
            index_code: 指数代码（如 'sh000300'）
            
        Returns:
            DataFrame with columns: date, open, close, high, low, vol
        """
        filename = f"{index_code}.json"
        filepath = os.path.join(self.data_dir, StrategyConfig.INDEX_HISTORY_DIR, filename)
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'records' in data:
            df = pd.DataFrame(data['records'])
        else:
            df = pd.DataFrame(data)
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
    
    def load_pe_data(self, index_code: str) -> pd.DataFrame:
        """
        加载PE估值数据（需要用户提供或从外部获取）
        
        数据源建议：
        1. 中证指数公司官网 - 提供官方指数估值数据
        2. 乐咕乐股 - https://legulegu.com/stockdata/market-pe
        3. 果仁网 - https://guorn.com/
        4. 东方财富Choice
        5. 第三方API
        
        数据格式要求：
        {
            "date": "2024-01-01",
            "pe": 12.5,          # 市盈率
            "pb": 1.5,           # 市净率（可选）
            "roe": 0.12          # ROE（可选，用于计算PEG）
        }
        
        Args:
            index_code: 指数代码
            
        Returns:
            DataFrame with columns: date, pe, pb (optional)
        """
        # TODO: 用户需要提供PE数据文件
        pe_file = os.path.join(self.data_dir, "pe_data", f"{index_code}_pe.json")
        
        if not os.path.exists(pe_file):
            return None
        
        with open(pe_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df


# ============================================
# PER分位计算模块
# ============================================

class PERPercentileCalculator:
    """PER分位计算器"""
    
    def __init__(self, window: int = StrategyConfig.PERCENTILE_WINDOW):
        self.window = window
    
    def calculate_percentile(self, series: pd.Series, window: int = None) -> pd.Series:
        """
        计算滚动分位数
        
        Args:
            series: PER序列
            window: 滚动窗口大小
            
        Returns:
            分位数序列（0-100）
        """
        if window is None:
            window = self.window
        
        # 计算滚动排名百分位
        def rank_percentile(x):
            if len(x) < 2:
                return np.nan
            return (x.rank().iloc[-1] - 1) / (len(x) - 1) * 100
        
        percentile = series.rolling(window=window, min_periods=window//2).apply(rank_percentile)
        
        return percentile
    
    def calculate_current_percentile(self, series: pd.Series, current_value: float) -> float:
        """
        计算当前值在历史序列中的分位
        
        Args:
            series: 历史PER序列
            current_value: 当前PER值
            
        Returns:
            分位数（0-100）
        """
        if len(series) < 2:
            return 50.0
        
        count_below = (series <= current_value).sum()
        percentile = count_below / len(series) * 100
        
        return percentile
    
    def get_pe_stats(self, pe_series: pd.Series, window: int = None) -> Dict:
        """
        获取PE统计信息
        
        Returns:
            {
                'current': 当前PE,
                'percentile': 当前分位,
                'mean': 均值,
                'median': 中位数,
                'std': 标准差,
                'min': 最小值,
                'max': 最大值,
                'low_20': 20%分位数,
                'high_80': 80%分位数
            }
        """
        if window:
            pe_series = pe_series.tail(window)
        
        current = pe_series.iloc[-1]
        
        return {
            'current': current,
            'percentile': self.calculate_current_percentile(pe_series[:-1], current),
            'mean': pe_series.mean(),
            'median': pe_series.median(),
            'std': pe_series.std(),
            'min': pe_series.min(),
            'max': pe_series.max(),
            'low_20': pe_series.quantile(0.2),
            'high_80': pe_series.quantile(0.8)
        }


# ============================================
# 信号生成模块
# ============================================

class SignalGenerator:
    """交易信号生成器"""
    
    def __init__(self, config: StrategyConfig = None):
        self.config = config or StrategyConfig()
    
    def generate_signal(self, 
                       current_percentile: float,
                       position_ratio: float = 0) -> int:
        """
        生成交易信号
        
        Args:
            current_percentile: 当前PER分位（0-100）
            position_ratio: 当前持仓比例
            
        Returns:
            信号: 1=买入, -1=卖出, 0=持有
        """
        # 强买入信号：极低分位且未满仓
        if current_percentile <= self.config.PER_EXTREME_LOW and position_ratio < 1.0:
            return 1
        
        # 强卖出信号：极高分位且有持仓
        if current_percentile >= self.config.PER_EXTREME_HIGH and position_ratio > 0:
            return -1
        
        # 普通买入信号：低分位且未满仓
        if current_percentile <= self.config.PER_LOW_THRESHOLD and position_ratio < 0.8:
            return 1
        
        # 普通卖出信号：高分位且有持仓
        if current_percentile >= self.config.PER_HIGH_THRESHOLD and position_ratio > 0.2:
            return -1
        
        return 0
    
    def generate_position_signal(self,
                                 pe_percentile: float,
                                 strategy_type: str = 'threshold') -> float:
        """
        生成目标仓位信号
        
        Args:
            pe_percentile: 当前PER分位（0-100）
            strategy_type: 策略类型
                - 'threshold': 阈值策略（离散）
                - 'linear': 线性策略（连续）
                - 'sigmoid': Sigmoid策略（平滑过渡）
                
        Returns:
            目标仓位比例（0-1）
        """
        if strategy_type == 'threshold':
            # 阈值策略：分段仓位
            if pe_percentile <= 10:
                return 1.0
            elif pe_percentile <= 20:
                return 0.8
            elif pe_percentile <= 50:
                return 0.5
            elif pe_percentile <= 80:
                return 0.2
            elif pe_percentile <= 90:
                return 0.1
            else:
                return 0.0
        
        elif strategy_type == 'linear':
            # 线性策略：仓位与分位线性反向
            return max(0, min(1, (100 - pe_percentile) / 100))
        
        elif strategy_type == 'sigmoid':
            # Sigmoid策略：平滑过渡
            import math
            # 中心点在50分位
            x = (pe_percentile - 50) / 20
            position = 1 / (1 + math.exp(x))
            return position
        
        return 0.5
    
    def generate_signals_batch(self,
                               pe_series: pd.Series,
                               window: int = None) -> pd.Series:
        """
        批量生成历史信号序列
        
        Args:
            pe_series: PER序列
            window: 计算分位的窗口
            
        Returns:
            目标仓位序列
        """
        calculator = PERPercentileCalculator(window)
        percentile_series = calculator.calculate_percentile(pe_series, window)
        
        # 使用Sigmoid策略生成仓位
        positions = percentile_series.apply(
            lambda x: self.generate_position_signal(x, 'sigmoid')
        )
        
        return positions


# ============================================
# 回测模块
# ============================================

class Backtester:
    """策略回测器"""
    
    def __init__(self, config: StrategyConfig = None):
        self.config = config or StrategyConfig()
        self.data_loader = DataLoader()
    
    def load_data(self, etf_code: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        加载回测数据
        
        Returns:
            (价格数据, PE数据)
        """
        # 加载价格数据
        price_df = self.data_loader.load_etf_history(etf_code, use_long=True)
        if price_df is None:
            return None, None
        
        # 加载PE数据
        # TODO: 需要用户提供PE数据
        pe_df = None
        
        return price_df, pe_df
    
    def run_backtest(self,
                     price_df: pd.DataFrame,
                     position_series: pd.Series) -> Dict:
        """
        执行回测
        
        Args:
            price_df: 价格数据
            position_series: 目标仓位序列（0-1）
            
        Returns:
            回测结果字典
        """
        # 对齐数据
        price_df = price_df.copy()
        price_df = price_df.set_index('date')
        
        # 合并仓位信号
        position_series.index = pd.to_datetime(position_series.index)
        merged = price_df.join(position_series.rename('target_position'), how='inner')
        
        if len(merged) == 0:
            return None
        
        # 计算每日收益
        merged['returns'] = merged['close'].pct_change()
        
        # 计算持仓变化
        merged['position'] = merged['target_position'].shift(1)  # T-1信号，T日执行
        merged['position_change'] = merged['position'].diff().abs()
        
        # 计算策略收益（考虑交易成本）
        merged['strategy_returns'] = merged['returns'] * merged['position']
        
        # 扣除交易成本
        merged['strategy_returns'] -= merged['position_change'] * self.config.TRANSACTION_COST
        
        # 计算累计收益
        merged['cum_returns'] = (1 + merged['returns']).cumprod()
        merged['strategy_cum_returns'] = (1 + merged['strategy_returns'].fillna(0)).cumprod()
        
        # 统计指标
        result = self._calculate_metrics(merged)
        
        return result
    
    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """计算绩效指标"""
        # 基准收益
        benchmark_return = df['cum_returns'].iloc[-1] - 1
        benchmark_annual = (df['cum_returns'].iloc[-1]) ** (252 / len(df)) - 1
        
        # 策略收益
        strategy_return = df['strategy_cum_returns'].iloc[-1] - 1
        strategy_annual = (df['strategy_cum_returns'].iloc[-1]) ** (252 / len(df)) - 1
        
        # 波动率
        benchmark_vol = df['returns'].std() * np.sqrt(252)
        strategy_vol = df['strategy_returns'].std() * np.sqrt(252)
        
        # 夏普比率
        rf = 0.02  # 无风险利率
        benchmark_sharpe = (benchmark_annual - rf) / benchmark_vol if benchmark_vol > 0 else 0
        strategy_sharpe = (strategy_annual - rf) / strategy_vol if strategy_vol > 0 else 0
        
        # 最大回撤
        def max_drawdown(cum_returns):
            peak = cum_returns.expanding(min_periods=1).max()
            drawdown = (cum_returns - peak) / peak
            return drawdown.min()
        
        benchmark_dd = max_drawdown(df['cum_returns'])
        strategy_dd = max_drawdown(df['strategy_cum_returns'])
        
        # 交易次数
        trades = (df['position_change'] > 0.01).sum()
        
        return {
            'period': {
                'start': df.index[0].strftime('%Y-%m-%d'),
                'end': df.index[-1].strftime('%Y-%m-%d'),
                'days': len(df)
            },
            'benchmark': {
                'total_return': f"{benchmark_return:.2%}",
                'annual_return': f"{benchmark_annual:.2%}",
                'volatility': f"{benchmark_vol:.2%}",
                'sharpe': f"{benchmark_sharpe:.2f}",
                'max_drawdown': f"{benchmark_dd:.2%}"
            },
            'strategy': {
                'total_return': f"{strategy_return:.2%}",
                'annual_return': f"{strategy_annual:.2%}",
                'volatility': f"{strategy_vol:.2%}",
                'sharpe': f"{strategy_sharpe:.2f}",
                'max_drawdown': f"{strategy_dd:.2%}",
                'trades': trades
            },
            'excess_return': f"{strategy_annual - benchmark_annual:.2%}"
        }


# ============================================
# 主程序
# ============================================

def main():
    """主程序入口"""
    
    print("=" * 60)
    print("PER分位择时策略框架")
    print("=" * 60)
    
    # 1. 加载标的池
    loader = DataLoader()
    etf_pool = loader.load_etf_pool()
    print(f"\n标的池已加载: {etf_pool['total']}只ETF")
    
    # 2. 数据需求说明
    print("\n" + "=" * 60)
    print("数据需求说明")
    print("=" * 60)
    print("""
本策略需要PE估值数据，请准备以下数据：

1. 数据格式（JSON）：
{
    "date": "2024-01-01",
    "pe": 12.5,
    "pb": 1.5
}

2. 数据存放路径：
   D:/QClaw_Trading/data/pe_data/sh000300_pe.json
   D:/QClaw_Trading/data/pe_data/sh000905_pe.json
   ...

3. 数据来源建议：
   - 中证指数公司官网（官方数据）
   - 乐咕乐股 https://legulegu.com/stockdata/market-pe
   - 果仁网 https://guorn.com/
   - 东方财富Choice终端
   
4. 需要的指数PE数据：
   - 沪深300 (sh000300)
   - 中证500 (sh000905)
   - 中证1000 (sh000852)
   - 科创50 (sh000688)
   - 创业板指 (sz399006)
   - 恒生指数 (hkHSI)
   - 纳斯达克100 (usNDX)
""")
    
    # 3. 示例：使用价格数据演示（模拟PE数据）
    print("\n" + "=" * 60)
    print("示例：沪深300ETF (510300)")
    print("=" * 60)
    
    price_df = loader.load_etf_history('510300', use_long=True)
    
    if price_df is not None:
        print(f"\n历史数据: {price_df['date'].min().strftime('%Y-%m-%d')} 至 {price_df['date'].max().strftime('%Y-%m-%d')}")
        print(f"数据量: {len(price_df)} 条")
        
        # 使用价格倒数模拟PE（仅作演示）
        # 实际应使用真实PE数据
        simulated_pe = 100 / price_df['close']
        
        calculator = PERPercentileCalculator()
        pe_stats = calculator.get_pe_stats(simulated_pe)
        
        print(f"\n模拟PE统计（仅演示）:")
        print(f"  当前值: {pe_stats['current']:.2f}")
        print(f"  历史分位: {pe_stats['percentile']:.1f}%")
        print(f"  均值: {pe_stats['mean']:.2f}")
        print(f"  标准差: {pe_stats['std']:.2f}")
        
        # 生成信号
        generator = SignalGenerator()
        position = generator.generate_position_signal(pe_stats['percentile'])
        print(f"\n建议仓位: {position:.0%}")
        
    else:
        print("\n无法加载历史数据")
    
    print("\n" + "=" * 60)
    print("下一步：请提供PE估值数据，以进行完整回测")
    print("=" * 60)


if __name__ == "__main__":
    main()
