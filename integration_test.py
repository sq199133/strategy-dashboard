"""多源降级 + 缓存 + 防御层 集成测试"""
import time
import json
from qclaw_stock_data import DataFetcher, normalize_tencent_kline, normalize_sina_kline

f = DataFetcher()

# 1. 拿ETF池前10只
pool_path = "D:/QClaw_Trading/data/etf_pool_V1_full.json"
with open(pool_path, encoding="utf-8") as fp:
    pool = json.load(fp)
codes = [item["code"] for item in pool["data"][:10]]
print(f"测试池: 前10只 {codes}\n")

# 2. 测试Sina主力源
print("=== Sina VIP 主力源 ===")
t0 = time.time()
ok = 0
for c in codes:
    r = f.kline(c, 50)
    if r:
        ok += 1
        print(f"  {c}: {r[-1]['date']} C:{r[-1]['close']}")
    else:
        print(f"  {c}: ❌")
t1 = time.time()
print(f"\n10只: {ok}/10成功, 耗时{t1-t0:.2f}s (含防御延迟)")
print(f"平均每只: {(t1-t0)/10*1000:.0f}ms (其中防封延迟占~70%)")

# 3. 缓存二次
print("\n=== 缓存命中 (二次) ===")
t2 = time.time()
for c in codes:
    f.kline(c, 50)
t3 = time.time()
print(f"10只: {t3-t2:.3f}s (纯内存读取)")

# 4. 全链路状态
print("\n=== 全链路状态 ===")
status = f.status()
print(f"缓存: {status['cache']}")
for name, s in status['sources'].items():
    print(f"  {name}: 成功率{s.get('success_rate', 0)}% ({s.get('total', 0)}次)")

# 5. Tencent 备选源验证
print("\n=== Tencent 备选源 ===")
f.defense.reset_streak('tencent_kline')
from qclaw_stock_data.sources import _tencent_kline
try:
    r = _tencent_kline('510500', ktype='day', defense=f.defense, datalen=320)
    if r:
        recs = normalize_tencent_kline(r['data'])
        print(f"  510500 Tencent: {len(recs)}条 最新{recs[-1]['date']} C:{recs[-1]['close']}")
except Exception as e:
    print(f"  510500 Tencent: 失败 {e}")
