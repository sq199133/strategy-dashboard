#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 akshare 更新10只ETF池数据"""

import json
import os
import akshare as ak
import pandas as pd
from datetime import datetime

HIST_DIR = r'D:\QClaw_Trading\data\history'

POOL = {
    '510050': 'SH50',
    '510300': 'HS300', 
    '510500': 'ZZ500',
    '512100': 'ZZ1000',
    '159915': 'CYB',
    '588000': 'KC50',
    '513500': 'SP500',
    '513100': 'NSDQ',
    '518880': 'GOLD',
    '162411': 'OIL'
}

def get_market(code):
    """判断市场"""
    if code.startswith('5') or code.startswith('6'):
        return 'sh'
    else:
        return 'sz'

def fetch_etf_akshare(code):
    """用 akshare 获取ETF历史数据"""
    try:
        # ETF数据可以用 stock_zh_a_hist
        # 但akshare有专门的ETF接口
        # 尝试 fund_etf_hist_em (ETF历史数据)
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date="20180101",
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq"
        )
        
        if df.empty:
            return None
            
        records = []
        for _, row in df.iterrows():
            records.append({
                'date': row['日期'],
                'open': float(row['开盘']),
                'close': float(row['收盘']),
                'high': float(row['最高']),
                'low': float(row['最低']),
                'vol': int(row['成交量']),
                'amount': int(row['成交额'])
            })
        
        return {
            'code': code,
            'name': df['名称'].iloc[0] if '名称' in df.columns else code,
            'records': records
        }
    except Exception as e:
        print(f'  {code} akshare失败: {e}')
        return None

def main():
    print('用 akshare 更新ETF数据...')
    print('=' * 60)
    
    for code in POOL:
        print(f'  {code} {POOL[code]}...', end=' ')
        data = fetch_etf_akshare(code)
        
        if data:
            path = os.path.join(HIST_DIR, f'{code}.json')
            
            # 检查是否需要追加数据
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                old_records = {r['date'] for r in old_data['records']}
                new_records = [r for r in data['records'] if r['date'] not in old_records]
                
                if new_records:
                    old_data['records'].extend(new_records)
                    old_data['records'].sort(key=lambda x: x['date'])
                    data = old_data
                    print(f'追加 {len(new_records)} 条 -> ', end='')
                else:
                    print(f'已最新 -> ', end='')
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            last_date = data['records'][-1]['date']
            print(f'{last_date} OK ({len(data["records"])} 条)')
        else:
            print('失败')
    
    print('=' * 60)
    print('更新完成！')

if __name__ == '__main__':
    main()
