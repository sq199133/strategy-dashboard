"""qclaw_stock_data v0.2.0 smoke test"""
import time
from qclaw_stock_data import DataFetcher, normalize_code, build_qt_code

f = DataFetcher()

print("=" * 60)
print("qclaw_stock_data v0.2.0 smoke test")
print("=" * 60)

# 1. code normalization
print("\n[1] code normalization")
tests = [
    ("159928", ("sz", "159928")),
    ("sh600519", ("sh", "600519")),
    ("sz000001", ("sz", "000001")),
    ("hk00700", ("hk", "00700")),
    ("usAAPL", ("us", "AAPL")),
    ("s_sh000001", ("index", "SH000001")),
]
ok = 0
for code, expected in tests:
    result = normalize_code(code)
    status = "OK" if result == expected else "FAIL"
    if result == expected:
        ok += 1
    print(f"  {status} {code:15s} -> {result} (expect:{expected})")
print(f"  Score: {ok}/{len(tests)}")

# 2. qt code build
print("\n[2] qt code build")
qt_tests = [
    ("sh600519", "sh600519"),
    ("sz000001", "sz000001"),
    ("s_sh000001", "s_sh000001"),
    ("hk00700", "hk00700"),
    ("usAAPL", "usAAPL"),
]
ok = 0
for code, expected in qt_tests:
    result = build_qt_code(code)
    status = "OK" if result == expected else "FAIL"
    if result == expected:
        ok += 1
    print(f"  {status} {code:15s} -> {result}")
print(f"  Score: {ok}/{len(qt_tests)}")

# 3. kline
print("\n[3] kline (sina 5000)")
t0 = time.time()
r = f.kline("159928", 5000)
t1 = time.time()
if r:
    print(f"  OK: {len(r)} rows [{r[0]['date']} -> {r[-1]['date']}] {t1-t0:.2f}s")
else:
    print("  FAIL")

# 4. batch quote (no hk/us, only cn)
print("\n[4] batch quote (tencent qt.gtimg.cn)")
t0 = time.time()
batch = ["sh600519", "sz000001", "sh510500", "sz159928", "sh518880", "s_sh000001"]
r = f.quote(batch)
t1 = time.time()
if r and isinstance(r, dict):
    print(f"  OK: {len(r)} items {t1-t0:.2f}s")
    for qt_code, rec in list(r.items())[:4]:
        name = str(rec.get('name', '?'))[:10]
        print(f"    {qt_code:12s} {name:12s} {rec.get('price')} chg:{rec.get('chg_pct')}% pe:{rec.get('pe_ttm')} pb:{rec.get('pb')}")
else:
    print(f"  FAIL (type={type(r)})")

# 5. single quote
print("\n[5] single quote")
t0 = time.time()
r = f.quote("sh600519")
t1 = time.time()
if r:
    print(f"  OK: {r.get('name')} {r.get('price')} pe:{r.get('pe_ttm')} pb:{r.get('pb')} {t1-t0:.2f}s")
else:
    print("  FAIL")

# 6. index
print("\n[6] index")
for idx_code in ["s_sh000001", "s_sh000300", "s_sz399006"]:
    t0 = time.time()
    r = f.index(idx_code)
    t1 = time.time()
    if r:
        print(f"  OK: {r.get('name')} {r.get('price')} ({r.get('chg_pct')}%) pe:{r.get('pe')} pb:{r.get('pb')} {t1-t0:.2f}s")
    else:
        print(f"  FAIL: {idx_code}")

# 7. cache
print("\n[7] cache")
t0 = time.time()
for c in ["sh600519", "sz000001", "sh510500"]:
    f.quote(c)
t1 = time.time()
t2 = time.time()
for c in ["sh600519", "sz000001", "sh510500"]:
    f.quote(c)
t3 = time.time()
print(f"  first 3: {t1-t0:.3f}s | cached 3: {t3-t2:.3f}s (first should be slower)")

# 8. health
print("\n[8] health status")
status = f.status()
print(f"  cache: {status['cache']}")
for name, s in status['sources'].items():
    print(f"  {name}: {s.get('success_rate', 0)}% total:{s.get('total')} broken:{s.get('circuit_broken')}")

print("\n" + "=" * 60)
print("Done")
