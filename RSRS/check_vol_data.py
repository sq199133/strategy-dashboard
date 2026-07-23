"""查看指数数据结构，确认有volume字段"""
import akshare as ak
import warnings; warnings.filterwarnings('ignore')

# 检查 A股指数 数据字段
print('=== A股指数 stock_zh_index_daily ===')
df = ak.stock_zh_index_daily(symbol='sh000300')
print(f'列: {list(df.columns)}')
print(f'类型: {df.dtypes.to_dict()}')
print(f'样本:\n{df.head(3).to_string()}')
print(f'volume 统计: {df["volume"].describe()}')

# 检查 美股指数
print(f'\n=== 美股指数 index_us_stock_sina ===')
df2 = ak.index_us_stock_sina(symbol='.INX')
print(f'列: {list(df2.columns)}')
print(f'类型: {df2.dtypes.to_dict()}')
print(f'样本:\n{df2.head(3).to_string()}')
vol_cols = [c for c in df2.columns if 'vol' in c.lower() or 'volume' in c.lower()]
print(f'volume 列: {vol_cols}')
if not vol_cols:
    print('❌ 美股指数无volume数据')
