#!/usr/bin/env python3
"""
ETF波动性分析 - 基于本地数据
"""
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

data_dir = r"D:\QClaw_Trading\data\history"

# 加载ETF列表
with open(r"D:\QClaw_Trading\data\etf_pool_V1_full.json", "r", encoding="utf-8") as f:
    pool = json.load(f)

etf_pool = {e['code']: e for e in pool['data']}

# 扫描本地数据
files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
etf_files = {}

for f in files:
    # 解析代码
    code = f.replace('sh', '').replace('sz', '').replace('.json', '')
    etf_files[code] = os.path.join(data_dir, f)

print(f"找到 {len(etf_files)} 只ETF历史数据")

def load_etf(code):
    """加载ETF数据"""
    path = etf_files.get(code)
    if not path:
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'records' in data and len(data.get('records', [])) > 0:
            df = pd.DataFrame(data['records'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            df['volume'] = df['vol'].astype(float)
            return df
    except Exception as e:
        print(f"Error loading {code}: {e}")
    return None

def calc_volatility(df):
    """计算波动性指标"""
    if df is None or len(df) < 60:
        return None
    
    try:
        # 日收益率
        df = df.copy()
        df['return'] = df['close'].pct_change()
        df = df.dropna()
        
        if len(df) < 60:
            return None
        
        # 年化波动率
        annual_vol = df['return'].std() * np.sqrt(252) * 100
        
        # ATR %
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        tr = np.maximum(high - low, np.abs(np.diff(close, prepend=close[0])))
        atr = np.mean(tr[-14:]) / close[-1] * 100 if len(tr) >= 14 else 0
        
        # 250日波动范围
        if len(df) >= 250:
            recent = df.tail(250)
        else:
            recent = df
        
        price_range = (recent['close'].max() - recent['close'].min()) / recent['close'].min() * 100
        
        # 最大回撤
        cummax = df['close'].cummax()
        drawdown = (df['close'] - cummax) / cummax
        max_dd = drawdown.min() * 100
        
        return {
            'annual_vol': round(annual_vol, 1),
            'atr_pct': round(atr, 1),
            'price_range': round(price_range, 1),
            'max_drawdown': round(max_dd, 1),
            'data_points': len(df)
        }
    except Exception as e:
        return None

# 计算所有ETF波动性
results = []
for code, path in etf_files.items():
    etf_info = etf_pool.get(code, {})
    name = etf_info.get('name', code)
    category = etf_info.get('category', '')
    
    df = load_etf(code)
    vol = calc_volatility(df)
    
    if vol:
        results.append({
            'code': code,
            'name': name,
            'category': category,
            **vol
        })

print(f"有效数据: {len(results)} 只")

# 按波动率排序
results.sort(key=lambda x: x['annual_vol'], reverse=True)

# 显示Top 30
print("\n" + "="*90)
print("ETF波动性分析 - Top 30 高波动ETF (真实数据)")
print("="*90)
print(f"{'代码':<8} {'名称':<20} {'类别':<12} {'年化波动':>8} {'ATR':>6} {'250日波动':>10} {'最大回撤':>10}")
print("-"*90)

for r in results[:30]:
    print(f"{r['code']:<8} {r['name'][:18]:<20} {r['category'][:10]:<12} {r['annual_vol']:>7.1f}% {r['atr_pct']:>5.1f}% {r['price_range']:>9.1f}% {r['max_drawdown']:>9.1f}%")

# 保存结果
df_out = pd.DataFrame(results)
df_out.to_csv(r"D:\QClaw_Trading\data\etf_volatility_real.csv", index=False, encoding="utf-8-sig")

# 保存高波动ETF列表用于回测
high_vol_etfs = [r['code'] for r in results[:20] if r['annual_vol'] > 25]
with open(r"D:\QClaw_Trading\data\high_vol_etfs.json", "w") as f:
    json.dump(high_vol_etfs, f)

print(f"\n结果已保存到 volatility_real.csv")
print(f"高波动ETF用于回测: {high_vol_etfs}")