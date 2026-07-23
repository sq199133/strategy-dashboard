"""测试AKShare全球指数接口"""
import akshare as ak

# 全球指数名称表
print('=== 全球指数名称表 ===')
try:
    names = ak.index_global_name_table()
    print(f'  共{len(names)}条')
    # 看美国/欧洲/亚太主要指数
    for k in ['S&P 500','NASDAQ','Dow Jones','DAX','FTSE','Nikkei','Hang Seng','A50','黄金','原油']:
        m = names[names['指数名称'].str.contains(k, case=False, na=False)]
        if len(m):
            for _, r in m.iterrows():
                print(f'  {r["指数代码"]:<12} {r["指数名称"]}')
except Exception as e:
    print(f'  ERR: {str(e)[:100]}')

print()
print('=== 全球指数历史(Sina) ===')
for sym, name in [('.SPX','标普500'),('.IXIC','纳斯达克'),('.DJI','道琼斯'),
                   ('.HSI','恒生'),('XAU','黄金现货'),('CL','原油')]:
    try:
        df = ak.index_global_hist_sina(symbol=sym)
        print(f'  {name:<8}({sym:<8}): {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
        print(f'          首:{df.iloc[0]["close"]:.2f}  末:{df.iloc[-1]["close"]:.2f}')
    except Exception as e:
        print(f'  {name:<8}({sym:<8}): ERR {str(e)[:100]}')

print()
print('=== 全球指数历史(东方财富) ===')
for sym in ['.SPX','.IXIC','.DJI','.HSI','GC.CMX','CL.NYM']:
    try:
        df = ak.index_global_hist_em(symbol=sym)
        print(f'  {sym:<12}: {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
        print(f'          首:{df.iloc[0]["close"]:.2f}  末:{df.iloc[-1]["close"]:.2f}')
    except Exception as e:
        print(f'  {sym:<12}: ERR {str(e)[:100]}')
