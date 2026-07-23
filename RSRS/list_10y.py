import json, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

pool = json.load(open("D:\\QClaw_Trading\\etf_pool_cn.json", "r", encoding="utf-8"))
etf_map = {}
for p in pool:
    etf_map[p["\u4ee3\u7801"]] = p.get("\u540d\u79f0", "?")

d = "D:\\QClaw_Trading\\data\\history"
results = []
for f in os.listdir(d):
    if not f.endswith(".json"):
        continue
    code = f.replace(".json", "")
    raw = json.load(open(os.path.join(d, f), "r", encoding="utf-8"))
    r = raw["records"] if isinstance(raw, dict) else raw
    n = len(r)
    if n < 2500:
        continue
    name = etf_map.get(code, "?")
    first, last = r[0]["date"], r[-1]["date"]
    results.append((code, name, n, first, last))

results.sort(key=lambda x: -x[2])

existing = {"510300","510050","159902","159949","512100","159928",
            "512800","512400","512200","510160","518880","159905","510810"}

print("  {:<6}  {:<16}  {:>5}  {:>4}  {:<22}  {}".format(
    "\u4ee3\u7801", "\u540d\u79f0", "\u8bb0\u5f55", "\u5e74\u9650", "\u671f\u95f4", "\u72b6\u6001"))
print("  " + "-"*75)
for code, name, n, first, last in results:
    yrs = round(n / 252, 1)
    tag = " [已有]" if code in existing else ""
    print("  {:>6}  {:<16}  {:>5}  {:>4}\u5e74  {:<10}~{} {}".format(
        code, name, n, yrs, first, last, tag))

a = len([x for x in results if x[0] in existing])
b = len([x for x in results if x[0] not in existing])
print("\n  共{}只  已有{}只  待选{}只".format(len(results), a, b))
