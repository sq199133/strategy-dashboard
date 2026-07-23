"""修复yfinance SSL并测试"""
import certifi, os
os.environ['SSL_CERT_FILE'] = certifi.where()
print(f'certifi: {certifi.where()}')

import yfinance as yf

for sym,name in [('GC=F','黄金期货'),('CL=F','WTI原油'),('BZ=F','布伦特原油')]:
    try:
        t = yf.Ticker(sym)
        df = t.history(period='max')
        s = df['Close']
        print(f'{name:<8}({sym:<6}): {len(df)}行 {df.index[0].date()} ~ {df.index[-1].date()}')
        print(f'          首:{s.iloc[0]:.2f}  末:{s.iloc[-1]:.2f}')
    except Exception as e:
        print(f'{name:<8}({sym:<6}): {str(e)[:100]}')
