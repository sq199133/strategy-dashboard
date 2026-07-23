# -*- coding: utf-8 -*-
"""
获取全市场PB数据
"""
import akshare as ak
import pandas as pd
import json
import os

output_dir = 'D:/QClaw_Trading/data/pe_data'
os.makedirs(output_dir, exist_ok=True)

print('Fetching A-share market PB data...')
df = ak.stock_market_pb_lg()

# 打印列名
print(f'列名: {df.columns.tolist()}')
print(f'前3行:\n{df.head(3)}')

# 重命名列（根据实际列数调整）
# 假设列顺序: 日期, 指数值, 平均PB, 加权平均PB, PB百分位
df = df.rename(columns={
    df.columns[0]: 'date',
    df.columns[1]: 'index_value',
    df.columns[2]: 'pb_avg',
    df.columns[3]: 'pb_weighted',
    df.columns[4]: 'pb_percentile'
})

# 只保留需要的列
df = df[['date', 'index_value', 'pb_avg', 'pb_weighted', 'pb_percentile']]

df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
df = df.sort_values('date')

output_file = os.path.join(output_dir, 'a_market_pb.json')
records = df.to_dict('records')
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f'Saved to: {output_file}')
print(f'Records: {len(df)}')
print(f'Date range: {df["date"].iloc[0]} to {df["date"].iloc[-1]}')
print(f'\nLatest data:')
print(df.tail(10).to_string())
