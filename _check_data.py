# -*- coding: utf-8 -*-
import os
import pandas as pd

# 检查财务数据结构
fin_dir = r'D:\QClaw_Trading\data\baostock_stocks\fin'
price_dir = r'D:\QClaw_Trading\data\baostock_stocks\price'

fin_files = os.listdir(fin_dir)
price_files = os.listdir(price_dir)

print(f'财务文件: {len(fin_files)}个, 行情文件: {len(price_files)}个')

# 读一个财务文件看结构
df_fin = pd.read_csv(os.path.join(fin_dir, fin_files[0]))
print(f'\n=== 财务数据({fin_files[0]}) ===')
print(f'字段: {list(df_fin.columns)}')
print(f'行数: {len(df_fin)}')
print(df_fin.tail(4).to_string())

# 读一个行情文件看结构
df_price = pd.read_csv(os.path.join(price_dir, price_files[0]))
print(f'\n=== 行情数据({price_files[0]}) ===')
print(f'字段: {list(df_price.columns)}')
print(f'行数: {len(df_price)}')
print(df_price.tail(4).to_string())

# 检查constituents
df_const = pd.read_csv(r'D:\QClaw_Trading\data\baostock_stocks\constituents.csv')
print(f'\n=== 成分股列表 ===')
print(f'总数: {len(df_const)}')
print(df_const.head(3).to_string())
