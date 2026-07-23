# -*- coding: utf-8 -*-
"""验证akshare指数PE/PB接口"""
import sys
sys.path.insert(0, r'D:\QClaw_Trading')
import qclaw_stock_data as qsd

# 查看akshare_index_pe_pb函数
fn = qsd.INDEX_SOURCES[1]['fn']
print('函数签名:', fn.__code__.co_varnames[:fn.__code__.co_argcount])
import inspect
print(inspect.getsource(fn)[:2000])
