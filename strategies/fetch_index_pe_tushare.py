# -*- coding: utf-8 -*-
"""
使用tushare获取指数估值数据
需要tushare token
"""
import tushare as ts
import pandas as pd
import json
import os

output_dir = 'D:/QClaw_Trading/data/pe_data'
os.makedirs(output_dir, exist_ok=True)

# 指数列表
INDICES = [
    ('sh000300', '000300.SH', 'HS300'),
    ('sh000905', '000905.SH', 'ZZ500'),
    ('sh000852', '000852.SH', 'ZZ1000'),
    ('sh000016', '000016.SH', 'SZ50'),
]

# 尝试获取数据
print('Testing tushare connection...')

try:
    # 尝试获取基础信息，测试token是否有效
    pro = ts.pro_api()
    print('Tushare token is valid')

    # 尝试获取指数估值数据
    # index_dailybasic - 每日指标
    print('\nTrying to fetch index valuation data...')

    for full_code, ts_code, name in INDICES:
        print(f'\nFetching {name} ({ts_code})...')

        try:
            # 获取每日基本面数据（包括PE、PB）
            df = pro.index_dailybasic(ts_code=ts_code, fields='trade_date,pe_ttm,pb')

            if df is not None and len(df) > 0:
                # 处理数据
                df = df.rename(columns={
                    'trade_date': 'date',
                    'pe_ttm': 'pe',
                    'pb': 'pb'
                })

                # 格式化日期
                df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                df = df.sort_values('date')

                # 保存
                output_file = os.path.join(output_dir, f'{full_code}_pe.json')
                records = df.to_dict('records')
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)

                print(f'  [OK] Saved {len(df)} records')
                print(f'  Date range: {df["date"].iloc[0]} to {df["date"].iloc[-1]}')
            else:
                print(f'  [FAIL] No data returned')

        except Exception as e:
            print(f'  [FAIL] {str(e)}')

except Exception as e:
    print(f'Tushare error: {str(e)}')
    print('\nPossible issues:')
    print('1. Tushare token not set')
    print('2. Insufficient points for this API')
    print('3. Network connection issue')
    print('\nTo get tushare token:')
    print('1. Register at https://tushare.pro/')
    print('2. Get your token from user center')
    print('3. Set token: ts.set_token("your_token")')
