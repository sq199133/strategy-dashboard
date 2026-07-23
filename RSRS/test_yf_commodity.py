"""yfinance获取商品数据"""
import yfinance as yf

for sym,name in [('GC=F','黄金期货'),('CL=F','WTI原油'),('BZ=F','布伦特原油')]:
    try:
        t = yf.Ticker(sym)
        df = t.history(period='max')
        s = df['Close']
        print(f'{name:<8}({sym:<6}): {len(df)}行 {df.index[0].date()} ~ {df.index[-1].date()}')
        print(f'          首:{s.iloc[0]:.2f}  末:{s.iloc[-1]:.2f}')
    except Exception as e:
        print(f'{name:<8}({sym:<6}): {str(e)[:80]}')

print()
# 也可以用^XAU/USD for gold spot
# 看是否有黄金现货指数
try:
    t = yf.Ticker('^XAU')
    df = t.history(period='max')
    s = df['Close']
    print(f'黄金现货(^XAU): {len(df)}行')
except:
    print('^XAU: 无数据')
