#!/usr/bin/env python3
"""Thorough check: find all data gaps and incomplete downloads."""
import json, time, random, requests
from pathlib import Path
from collections import Counter

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

# Step 1: Check all 195 ETFs
print("=" * 60)
print("DEEP CHECK: 195只ETF数据质量")
print("=" * 60)

issues = []

for e in pool["data"]:
    code = e["code"]
    name = e["name"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        issues.append((code, name, "MISSING", 0, ""))
        continue
    
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data.get("records", [])
    n = len(records)
    
    if n == 0:
        issues.append((code, name, "EMPTY", 0, ""))
        continue
    
    start = records[0]["date"]
    end = records[-1]["date"]
    
    # a) 记录太少 (< 100)
    if n < 100:
        issues.append((code, name, f"SHORT({n})", n, f"{start} ~ {end}"))
        continue
    
    # b) 检查价格数据是否完整 (open/close/high/low)
    r0 = records[0]
    missing_fields = [k for k in ["open", "close", "high", "low"] if r0.get(k, 0) == 0]
    if missing_fields and n < 300:
        issues.append((code, name, f"NO_{'_'.join(missing_fields).upper()}", n, f"{start}"))
        continue

print(f"\n共发现 {len(issues)} 个问题标的：")
for code, name, desc, n, span in sorted(issues, key=lambda x: x[1]):
    print(f"  [{desc}] {code} {name}: {span}")

# Step 2: Try to fix them via Sina API
if issues:
    print(f"\n{'=' * 60}")
    print(f"尝试补充 {len(issues)} 只有问题的标的...")
    print(f"{'=' * 60}")
    
    def code_market(c):
        if str(c).strip().startswith(("6", "5")):
            return "sh"
        return "sz"
    
    success = 0
    for i, (code, name, desc, n, span) in enumerate(issues):
        print(f"  [{i+1}/{len(issues)}] {code} {name} ...", end="", flush=True)
        time.sleep(0.5 + random.random() * 1)
        
        try:
            market = code_market(code)
            url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
                   f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=1500")
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and r.text.strip() and len(r.text) > 10:
                sina_data = r.json()
                if sina_data:
                    records = []
                    for row in sina_data:
                        day = row["day"].split()[0]
                        records.append({
                            "date": day,
                            "open": float(row["open"]),
                            "close": float(row["close"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "vol": int(float(row.get("volume", 0))),
                            "amount": int(float(row.get("amount", 0))),
                            "chg": 0.0
                        })
                    records.sort(key=lambda r: r["date"])
                    
                    if len(records) > n:
                        out = {"code": code, "name": name, "records": records}
                        (HISTORY / f"{code}.json").write_text(
                            json.dumps(out, ensure_ascii=False), encoding="utf-8")
                        print(f" ✓ {len(records)}条 ({records[0]['date']} ~ {records[-1]['date']})")
                        success += 1
                    else:
                        print(f" — 只有{len(records)}条, 不比已有({n})多")
                else:
                    print(f" ✗ 返回空数据")
            else:
                print(f" ✗ HTTP {r.status_code}")
        except Exception as ex:
            print(f" ✗ {str(ex)[:50]}")
    
    print(f"\n补充完成: {success}/{len(issues)}")

# Step 3: Final summary
print(f"\n{'=' * 60}")
print("最终状态")
print(f"{'=' * 60}")

remaining_issues = 0
for e in pool["data"]:
    code = e["code"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        print(f"  MISSING: {code} {e['name']}")
        remaining_issues += 1
        continue
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data.get("records", [])
    if len(records) < 100:
        print(f"  SHORT({len(records)}): {code} {e['name']} {records[0]['date']}~{records[-1]['date']}")
        remaining_issues += 1

print(f"\n剩余问题: {remaining_issues}/{len(pool)}")

# Year distribution
print(f"\n开始年份分布:")
years = Counter()
for e in pool["data"]:
    fp = HISTORY / f"{e['code']}.json"
    if not fp.exists():
        continue
    records = json.loads(fp.read_text(encoding="utf-8")).get("records", [])
    if records:
        years[records[0]["date"][:4]] += 1
for y in sorted(years):
    print(f"  {y}: {years[y]}只")

# Record count distribution
print(f"\n记录数分布:")
buckets = Counter()
total_rec = 0
for e in pool["data"]:
    fp = HISTORY / f"{e['code']}.json"
    if not fp.exists():
        continue
    n = len(json.loads(fp.read_text(encoding="utf-8")).get("records", []))
    total_rec += n
    if n < 100: buckets["<100"] += 1
    elif n < 200: buckets["100-199"] += 1
    elif n < 500: buckets["200-499"] += 1
    elif n < 1000: buckets["500-999"] += 1
    elif n < 2000: buckets["1000-1999"] += 1
    else: buckets["2000+"] += 1
for b in ["<100", "100-199", "200-499", "500-999", "1000-1999", "2000+"]:
    if b in buckets:
        print(f"  {b}: {buckets[b]}只")
print(f"总记录数: {total_rec:,}")

print("\n✅ 完成")
