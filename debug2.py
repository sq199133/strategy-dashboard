# -*- coding: utf-8 -*-
import pandas as pd
dates = pd.date_range('2019-01-01','2026-07-10',freq='5D')
print('dates freq:', dates.freq)
print('dates count:', len(dates))
print('first 3:', dates[:3])
bt_start = pd.Timestamp('2020-01-01')
bt_end = pd.Timestamp('2026-07-10')
mask = (dates >= bt_start) & (dates <= bt_end)
print('mask true count:', mask.sum())
print('filtered dates sample:', list(dates[mask][:3]))
