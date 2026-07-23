import json

# 159949 CYB50
raw = json.load(open("D:\\QClaw_Trading\\data\\history\\159949.json", "r", encoding="utf-8"))
r = raw["records"] if isinstance(raw, dict) else raw
print("=== 159949 CYB50 最近10日 ===")
for rec in r[-10:]:
    d = rec["date"]
    o = rec["open"]
    h = rec["high"]
    l = rec["low"]
    c = rec["close"]
    v = rec.get("vol", "?")
    print(f"  {d}  o={o} h={h} l={l} c={c}  vol={v}")

# W25
jun15 = r[-2]
jun16 = r[-1]
ret = (float(jun16["close"]) / float(jun15["close"]) - 1) * 100
print(f"\nW25 (Jun 15-16) CYB50:  {jun15['close']} -> {jun16['close']}  = {ret:+.1f}%")

# HS300
raw2 = json.load(open("D:\\QClaw_Trading\\data\\history\\510300.json", "r", encoding="utf-8"))
r2 = raw2["records"] if isinstance(raw2, dict) else raw2
print("\n=== 沪深300 最近5日 ===")
for rec in r2[-5:]:
    print(f"  {rec['date']}  close={rec['close']}")

# W24回撤对比
jun8_c = [x for x in r if x["date"] == "2026-06-08"]
jun12_c = [x for x in r if x["date"] == "2026-06-12"]
if jun8_c and jun12_c:
    c1, c2 = float(jun8_c[0]["close"]), float(jun12_c[0]["close"])
    print(f"\nW24 CYB50:  {c1} -> {c2}  = {(c2/c1-1)*100:+.1f}%")

jun8_300 = [x for x in r2 if x["date"] == "2026-06-08"]
jun12_300 = [x for x in r2 if x["date"] == "2026-06-12"]
if jun8_300 and jun12_300:
    c1, c2 = float(jun8_300[0]["close"]), float(jun12_300[0]["close"])
    print(f"W24 HS300:  {c1} -> {c2}  = {(c2/c1-1)*100:+.1f}%")
