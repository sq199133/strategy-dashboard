#!/usr/bin/env python3
"""
ETF波动性分析 - 快速版
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import concurrent.futures
import time

def get_etf_hist_fast(code):
    """快速获取单只ETF数据"""
    try:
        if len(code) == 6:
            if code.startswith('5') or code.startswith('1'):
                symbol = f"sh{code}"
            else:
                symbol = f"sz{code}"
            
            df = ak.stock_zh_a_hist(
                symbol=symbol, 
                period="daily", 
                start_date=(datetime.now() - timedelta(days=300)).strftime("%Y%m%d"), 
                end_date=datetime.now().strftime("%Y%m%d"), 
                adjust="qfq"
            )
            if df is not None and len(df) > 60:
                return code, df
    except:
        pass
    return code, None

def calc_volatility(code, df):
    """计算波动性指标"""
    if df is None:
        return None
    
    try:
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close', 
            '最高': 'high', '最低': 'low', '成交量': 'volume'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').dropna()
        
        if len(df) < 60:
            return None
        
        df['daily_return'] = df['close'].pct_change()
        
        # 年化波动率
        annual_vol = df['daily_return'].std() * np.sqrt(252) * 100
        
        # 平均真实波幅 ATR %
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        atr = np.mean(tr[-14:]) / np.mean(close[-14:]) * 100 if len(tr) >= 14 else 0
        
        # 250日价格波动范围
        if len(df) >= 250:
            price_range = (df['close'].max() - df['close'].min()) / df['close'].min() * 100
        else:
            price_range = (df['close'].max() - df['close'].min()) / df['close'].min() * 100
        
        # 最大回撤
        cummax = df['close'].cummax()
        drawdown = (df['close'] - cummax) / cummax
        max_dd = drawdown.min() * 100
        
        return {
            'code': code,
            'annual_vol': round(annual_vol, 2),
            'atr_pct': round(atr, 2),
            'price_range': round(price_range, 2),
            'max_drawdown': round(max_dd, 2),
            'close': round(df['close'].iloc[-1], 3),
            'data_points': len(df)
        }
    except Exception as e:
        print(f"Error {code}: {e}")
        return None

def get_name_from_pool(code):
    """从标的池获取名称"""
    for etf in etf_pool:
        if etf['code'] == code:
            return etf['name'], etf.get('category', '')
    return code, ''

# 加载ETF列表
with open(r"D:\QClaw_Trading\data\etf_pool_V1_full.json", "r", encoding="utf-8") as f:
    data = json.load(f)

etf_pool = data['data']
etf_codes = [e['code'] for e in etf_pool]

print(f"开始获取 {len(etf_codes)} 只ETF数据...")

# 并行获取数据
results = []
batch_size = 20

for batch_start in range(0, min(len(etf_codes), 100), batch_size):
    batch_codes = etf_codes[batch_start:batch_start + batch_size]
    print(f"处理批次 {batch_start//batch_size + 1}: {batch_codes[:3]}...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_etf_hist_fast, code): code for code in batch_codes}
        
        for future in concurrent.futures.as_completed(futures):
            code, df = future.result()
            if df is not None:
                vol = calc_volatility(code, df)
                if vol:
                    name, cat = get_name_from_pool(code)
                    vol['name'] = name
                    vol['category'] = cat
                    results.append(vol)
    
    print(f"已完成 {min(batch_start + batch_size, 100)}/{min(len(etf_codes), 100)}")

if results:
    df_vol = pd.DataFrame(results)
    df_vol = df_vol.sort_values('annual_vol', ascending=False)
    
    print("\n" + "="*80)
    print("波动性排名 Top 30")
    print("="*80)
    
    top30 = df_vol.head(30)
    for i, row in top30.iterrows():
        print(f"{row['code']} {row['name'][:15]:<15} | 年化波动:{row['annual_vol']:>6.1f}% | ATR:{row['atr_pct']:>5.1f}% | 250日波动:{row['price_range']:>6.1f}% | 最大回撤:{row['max_drawdown']:>7.1f}%")
    
    # 保存
    df_vol.to_csv(r"D:\QClaw_Trading\data\etf_volatility.csv", index=False, encoding="utf-8-sig")
    print(f"\n数据已保存，共计{len(df_vol)}只ETF")
else:
    print("未获取到有效数据")