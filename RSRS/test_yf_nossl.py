"""绕过yfinance SSL问题"""
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import yfinance as yf
import numpy as np

for sym,name in [('GC=F','黄金期货'),('CL=F','WTI原油'),('BZ=F','布伦特原油')]:
    try:
        t = yf.Ticker(sym)
        df = t.history(period='max')
        s = df['Close'].dropna()
        print(f'{name:<8}({sym:<6}): {len(df)}行 {df.index[0].date()} ~ {df.index[-1].date()}')
        print(f'          首:{s.iloc[0]:.2f}  末:{s.iloc[-1]:.2f}')
    except Exception as e:
        print(f'{name:<8}({sym:<6}): {str(e)[:100]}')
