# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\QClaw_Trading')
try:
    import qclaw_stock_data as qsd
    print('OK, attrs:', [x for x in dir(qsd) if not x.startswith('_')])
except Exception as e:
    print('FAIL:', type(e).__name__, str(e))
