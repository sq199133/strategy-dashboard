"""MVP smoke test - 验证 DataFetcher 全链路"""
import time
from qclaw_stock_data import DataFetcher

f = DataFetcher()

# 1. 全历史
print("=== 全历史(5000条)===")
r = f.kline("159928", 5000)
print(f"条数: {len(r)}")
print(f"首: {r[0]['date']} C:{r[0]['close']}")
print(f"末: {r[-1]['date']} C:{r[-1]['close']}")

# 2. 缓存命中
print()
print("=== 缓存验证 ===")
t1 = time.time()
r1 = f.kline("159928", 50)
t2 = time.time()
r2 = f.kline("159928", 50)
t3 = time.time()
print(f"首次:{t2-t1:.3f}s, 二次(缓存):{t3-t2:.3f}s")
print(f"数据一致: {r1[-1] == r2[-1]}")

# 3. 多只批量
print()
print("=== 5只批量 ===")
codes = ["510500", "159928", "510050", "159901", "600519"]
for c in codes:
    r = f.kline(c, 50)
    if r:
        print(f"  {c}: {len(r)}条 最新:{r[-1]['date']} C:{r[-1]['close']}")
    else:
        print(f"  {c}: 获取失败")

# 4. 状态报告
print()
print("=== 健康状态 ===")
import json
status = f.status()
print(f"缓存: {status['cache']}")
print(f"源状态: {json.dumps(status['sources'], ensure_ascii=False, indent=2)}")
