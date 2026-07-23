#!/usr/bin/env python3
"""
ETF波段策略 - 完整策略代码
策略A: 布林带突破策略
策略B: 趋势突破策略
策略C: 均线交叉策略
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

# ============ 配置区 ============
DATA_DIR = r"D:\QClaw_Trading\data\history"
INITIAL_CAPITAL = 100000  # 初始资金
STOP_LOSS = 0.06          # 止损6%（2026-05-22优化后参数）
TAKE_PROFIT = 0.10        # 止盈10%（2026-05-22优化后参数）

# ============ 数据加载 ============
def load_etf(code):
    """加载ETF历史数据"""
    for prefix in ['sh', 'sz']:
        path = os.path.join(DATA_DIR, f"{prefix}{code}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'records' in data:
                df = pd.DataFrame(data['records'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                return df
    return None

# ============ 指标计算 ============
def calculate_indicators(df):
    """计算技术指标"""
    # 布林带 (20日, 2倍标准差)
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['ma20'] + 2 * df['std20']
    df['bb_lower'] = df['ma20'] - 2 * df['std20']
    
    # 均线
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20_long'] = df['close'].rolling(20).mean()
    
    # 20日高低点
    df['high20'] = df['high'].rolling(20).max()
    df['low20'] = df['low'].rolling(20).min()
    
    # ATR
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.abs(df['close'] - df['close'].shift(1))
    )
    df['atr'] = df['tr'].rolling(14).mean()
    
    return df

# ============ 策略A: 布林带突破 ============
class BollingerStrategy:
    """
    布林带突破策略
    
    买入条件:
        收盘价突破布林带上轨（前一日）
        
    卖出条件:
        1. 收盘价跌破布林带下轨（前一日）
        2. 或止损（下跌8%）
        3. 或止盈（上涨15%）
    """
    name = "布林带突破"
    
    @staticmethod
    def check_buy(df, i, position):
        if position > 0:
            return False
        # 前一日收盘在布林带内，当日突破上轨
        if (df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and 
            df['close'].iloc[i] > df['bb_upper'].iloc[i]):
            return True
        return False
    
    @staticmethod
    def check_sell(df, i, position, entry_price):
        if position == 0:
            return False, None
        
        close = df['close'].iloc[i]
        
        # 止损
        if close < entry_price * (1 - STOP_LOSS):
            return True, '止损'
        
        # 止盈
        if close > entry_price * (1 + TAKE_PROFIT):
            return True, '止盈'
        
        # 布林带下轨跌破
        if (df['close'].iloc[i-1] >= df['bb_lower'].iloc[i-1] and 
            close < df['bb_lower'].iloc[i]):
            return True, '信号卖出'
        
        return False, None

# ============ 策略B: 趋势突破 ============
class BreakoutStrategy:
    """
    趋势突破策略
    
    买入条件:
        收盘价突破20日最高价（前一日）
        
    卖出条件:
        1. 收盘价跌破20日最低价（前一日）
        2. 或止损（下跌8%）
        3. 或止盈（上涨15%）
    """
    name = "趋势突破"
    
    @staticmethod
    def check_buy(df, i, position):
        if position > 0:
            return False
        # 前一日收盘在20日高点下方，当日突破
        if (df['close'].iloc[i-1] <= df['high20'].iloc[i-1] and 
            df['close'].iloc[i] > df['high20'].iloc[i]):
            return True
        return False
    
    @staticmethod
    def check_sell(df, i, position, entry_price):
        if position == 0:
            return False, None
        
        close = df['close'].iloc[i]
        
        # 止损
        if close < entry_price * (1 - STOP_LOSS):
            return True, '止损'
        
        # 止盈
        if close > entry_price * (1 + TAKE_PROFIT):
            return True, '止盈'
        
        # 20日低点跌破
        if (df['close'].iloc[i-1] >= df['low20'].iloc[i-1] and 
            close < df['low20'].iloc[i]):
            return True, '信号卖出'
        
        return False, None

# ============ 策略C: 均线交叉 ============
class MAStrategy:
    """
    均线交叉策略
    
    买入条件:
        5日均线上穿20日均线（金叉）
        
    卖出条件:
        1. 5日均线下穿20日均线（死叉）
        2. 或止损（下跌8%）
        3. 或止盈（上涨15%）
    """
    name = "均线交叉"
    
    @staticmethod
    def check_buy(df, i, position):
        if position > 0:
            return False
        # 金叉
        if (df['ma5'].iloc[i-1] <= df['ma20_long'].iloc[i-1] and 
            df['ma5'].iloc[i] > df['ma20_long'].iloc[i]):
            return True
        return False
    
    @staticmethod
    def check_sell(df, i, position, entry_price):
        if position == 0:
            return False, None
        
        close = df['close'].iloc[i]
        
        # 止损
        if close < entry_price * (1 - STOP_LOSS):
            return True, '止损'
        
        # 止盈
        if close > entry_price * (1 + TAKE_PROFIT):
            return True, '止盈'
        
        # 死叉
        if (df['ma5'].iloc[i-1] >= df['ma20_long'].iloc[i-1] and 
            df['ma5'].iloc[i] < df['ma20_long'].iloc[i]):
            return True, '信号卖出'
        
        return False, None

# ============ 回测引擎 ============
class Backtester:
    """回测引擎"""
    
    def __init__(self, df, strategy, etf_name=""):
        self.df = df
        self.strategy = strategy
        self.etf_name = etf_name
        self.cash = INITIAL_CAPITAL
        self.shares = 0
        self.entry_price = 0
        self.trades = []
        self.equity_curve = []
        
    def run(self, start_idx=25):
        """运行回测"""
        for i in range(start_idx, len(self.df)):
            date = self.df['date'].iloc[i]
            close = self.df['close'].iloc[i]
            
            # 检查买入
            if self.shares == 0:
                if self.strategy.check_buy(self.df, i, self.shares):
                    self.shares = int(self.cash / close * 0.995)
                    self.entry_price = close
                    self.cash = self.cash - self.shares * close
                    self.trades.append({
                        'date': str(date.date()),
                        'action': '买入',
                        'price': float(close),
                        'shares': int(self.shares),
                        'signal': self.strategy.name
                    })
            
            # 检查卖出
            else:
                should_sell, reason = self.strategy.check_sell(
                    self.df, i, self.shares, self.entry_price
                )
                if should_sell:
                    ret = (close / self.entry_price - 1) * 100
                    self.cash = self.cash + self.shares * close
                    self.trades.append({
                        'date': str(date.date()),
                        'action': reason,
                        'price': float(close),
                        'shares': int(self.shares),
                        'return': float(ret)
                    })
                    self.shares = 0
                    self.entry_price = 0
            
            # 记录权益
            value = self.cash + self.shares * close
            self.equity_curve.append({
                'date': str(date.date()),
                'value': float(value)
            })
        
        # 最终结算
        final_value = self.cash + self.shares * self.df['close'].iloc[-1]
        return final_value, self.trades, self.equity_curve
    
    def summary(self, final_value):
        """输出统计摘要"""
        completed = [t for t in self.trades if 'return' in t]
        wins = [t for t in completed if t['return'] > 0]
        
        print(f"\n{'='*60}")
        print(f"ETF: {self.etf_name}")
        print(f"策略: {self.strategy.name}")
        print(f"{'='*60}")
        print(f"初始资金: {INITIAL_CAPITAL:,.0f}元")
        print(f"最终资金: {final_value:,.2f}元")
        print(f"总收益: {(final_value/INITIAL_CAPITAL-1)*100:+.2f}%")
        print(f"\n交易统计:")
        print(f"  总交易: {len(completed)}次")
        print(f"  盈利: {len(wins)}次")
        print(f"  亏损: {len(completed)-len(wins)}次")
        if completed:
            print(f"  胜率: {len(wins)/len(completed)*100:.1f}%")
            print(f"  平均收益: {np.mean([t['return'] for t in completed]):.2f}%")
            print(f"  最大盈利: {max([t['return'] for t in completed]):.2f}%")
            print(f"  最大亏损: {min([t['return'] for t in completed]):.2f}%")
        
        print(f"\n交易明细:")
        for t in self.trades:
            if t['action'] == '买入':
                print(f"  {t['date']} 买入 {t['shares']}股 @{t['price']:.3f}  [{t['signal']}]")
            else:
                print(f"  {t['date']} {t['action']} {t['shares']}股 @{t['price']:.3f}  收益:{t['return']:+.2f}%")

# ============ 主程序 ============
if __name__ == "__main__":
    # 选择ETF和策略
    ETF_CODE = "501225"  # 全球芯片LOF
    STRATEGY_TYPE = "bollinger"  # bollinger, breakout, ma
    
    # 加载数据
    print(f"加载 {ETF_CODE} 数据...")
    df = load_etf(ETF_CODE)
    if df is None:
        print("数据加载失败!")
        exit()
    
    # 计算指标
    df = calculate_indicators(df)
    
    # 选择策略
    strategies = {
        'bollinger': BollingerStrategy,
        'breakout': BreakoutStrategy,
        'ma': MAStrategy
    }
    strategy = strategies[STRATEGY_TYPE]()
    
    # 运行回测
    print(f"运行 {strategy.name} 策略回测...")
    bt = Backtester(df, strategy, ETF_CODE)
    final_value, trades, equity = bt.run()
    
    # 输出结果
    bt.summary(final_value)
    
    # 保存交易记录
    output = {
        'etf': ETF_CODE,
        'strategy': strategy.name,
        'initial_capital': INITIAL_CAPITAL,
        'final_value': float(final_value),
        'total_return': float((final_value/INITIAL_CAPITAL-1)*100),
        'config': {
            'stop_loss': STOP_LOSS,
            'take_profit': TAKE_PROFIT
        },
        'trades': trades,
        'equity_curve': equity
    }
    
    with open(f"D:\\QClaw_Trading\\data\\trade_log_{ETF_CODE}_{STRATEGY_TYPE}.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n交易记录已保存到 trade_log_{ETF_CODE}_{STRATEGY_TYPE}.json")