#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.6.2 因子回测：量价背离 + ATR动态仓位
IS: 2017-W01~2022-W52 (6年)
OOS: 2023-W01~2026-W27 (3.5年)
"""

import json, os, sys
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# === 配置 ===
POOL_FILE = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'
HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'
OUTPUT_DIR = r'D:\Qclaw_Trading\review'

# 策略参数（v4.6.2基线）
LB = 3
MA_S = 5
MA_L = 21
MAX_DEV = 15
TOP_N = 3
ATR_RATIO = 0.85
C_BONUS = 0.02
B1_BONUS = 0.00
VOL_RATIO_THRESH = 1.5  # 高量能过滤

# 测试参数
VOL_DIVERGENCE_N = [3, 4, 5]  # 价格新高N周，量能未新高则跳过
ATR_WEIGHT_METHODS = ['equal', 'inv_atr', 'inv_sqrt_atr']  # 仓位权重方法

# === 工具函数 ===
def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    etfs = data.get('data', data.get('etfs', []))
    return etfs

def load_weekly_data(code):
    """加载周线数据"""
    path = os.path.join(HISTORY_DIR, f'{code}.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        if isinstance(content, dict) and 'records' in content:
            return content['records']
        elif isinstance(content, list):
            return content
        else:
            return None
    except:
        return None

def calc_wk(data, end_week=None):
    """计算周线指标"""
    if end_week:
        data = [w for w in data if w['week'] <= end_week]
    if len(data) < MA_L + 1:
        return None
    
    n = len(data)
    cl = [w['close'] for w in data]
    hi = [w['high'] for w in data]
    lo = [w['low'] for w in data]
    vo = [w['vol'] for w in data]
    
    out = []
    for i in range(MA_L, n):
        ma5 = sum(cl[i-4:i+1]) / 5
        ma21 = sum(cl[i-20:i+1]) / 21
        
        mom = cl[i] / cl[i-LB] - 1 if i >= LB else 0
        mom1w = cl[i] / cl[i-1] - 1 if i >= 1 else 0
        mom8w = cl[i] / cl[i-8] - 1 if i >= 8 else 0
        
        score = 0.4 * mom1w + 0.4 * mom + 0.2 * mom8w
        
        dev = (cl[i] - ma21) / ma21
        
        # ATR
        atr_ratios = {}
        trs = []
        for j in range(max(0, i-20), i+1):
            h, l = hi[j], lo[j]
            pc = cl[j-1] if j > 0 else cl[j]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        atr14 = sum(trs[-14:]) / 14 if len(trs) >= 14 else sum(trs) / len(trs)
        atr21 = sum(trs) / 21 if len(trs) >= 21 else sum(trs) / len(trs)
        atr_ratio = atr14 / atr21 if atr21 > 0 else 1
        
        # 量比
        avg_vol10 = sum(vo[i-9:i+1]) / 10 if i >= 9 else vo[i]
        vol_ratio = vo[i] / avg_vol10 if avg_vol10 > 0 else 1
        
        # 量价背离检测
        vol_div = False
        for N in VOL_DIVERGENCE_N:
            if i >= N:
                price_high = cl[i] >= max(cl[i-N:i])  # 价格创N周新高
                vol_high = vo[i] >= max(vo[i-N:i])    # 量能创N周新高
                if price_high and not vol_high:
                    vol_div = True
                    break
        
        # C型形态
        ci = cl[i]
        oi = data[i]['open']
        body = abs(ci - oi)
        u_shadow = hi[i] - max(ci, oi)
        l_shadow = min(ci, oi) - lo[i]
        s2b = u_shadow / body if body > 0 else 99
        c_pattern = (
            ci > oi and s2b > 1.0 and l_shadow < body * 0.5
            and vol_ratio < 1.5 and ci > ma5 > ma21
            and (cl[i] / cl[i-20] - 1 < 0.5 if i >= 20 else False)
        )
        
        out.append({
            'week': data[i]['week'],
            'date_end': data[i]['date_end'],
            'close': cl[i],
            'ma5': ma5,
            'ma21': ma21,
            'mom': mom,
            'mom1w': mom1w,
            'mom8w': mom8w,
            'score': score,
            'dev': dev,
            'atr_ratio': atr_ratio,
            'vol_ratio': vol_ratio,
            'vol_divergence': vol_div,
            'c_pattern': c_pattern,
            'atr14': atr14,  # 用于ATR仓位管理
        })
    
    return out

def run_backtest(params):
    """运行回测"""
    etfs = load_pool()
    results = {}
    
    for etf in etfs:
        code = etf['code']
        data = load_weekly_data(code)
        if data is None or len(data) < MA_L + 1:
            continue
        
        wk = calc_wk(data)
        if wk is None or len(wk) == 0:
            continue
        
        # 按周模拟
        capital = 100000
        positions = {}  # {code: {'shares': x, 'cost': y, 'entry_week': z}}
        weekly_value = []
        
        for week_data in wk:
            week = week_data['week']
            
            # 卖出逻辑
            for pos_code in list(positions.keys()):
                pos = positions[pos_code]
                # 获取当前价格
                pos_wk = [w for w in wk if w['week'] == week]
                if not pos_wk:
                    continue
                price = pos_wk[0]['close']
                
                # 止损
                if price <= pos['cost'] * 0.92 or price <= pos['cost'] * 1.10:  # 简化
                    capital += price * pos['shares']
                    del positions[pos_code]
            
            # 买入逻辑（简化：每周调仓）
            # 实际应该在这里加入量价背离过滤和ATR仓位管理
            # 暂时跳过具体实现
            
            # 记录权益
            total_value = capital
            for pos_code, pos in positions.items():
                pos_wk = [w for w in wk if w['week'] == week]
                if pos_wk:
                    total_value += pos_wk[0]['close'] * pos['shares']
            weekly_value.append(total_value)
        
        results[code] = {'weekly_value': weekly_value}
    
    return results

if __name__ == '__main__':
    print('v4.6.2 因子回测：量价背离 + ATR动态仓位')
    print('=' * 60)
    
    # 由于完整实现较复杂，先输出测试框架
    print('Backtest framework created. Need to implement:')
    print('1. 量价背离过滤（vol_divergence flag）')
    print('2. ATR动态仓位权重（inv_atr / inv_sqrt_atr）')
    print('3. IS/OOS分离回测')
    print('4. 结果对比输出')
