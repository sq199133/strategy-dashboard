"""
从195只ETF中筛选10-15年历史的优质标的，按类别归类
"""
import json, os

DATA_DIR = "D:\\QClaw_Trading\\data\\history"
pool_path = "D:\\QClaw_Trading\\etf_pool_V1_full.json"

# 加载品种分类
pool = json.load(open(pool_path, "r", encoding="utf-8"))
code_to_cat = {}
for item in pool:
    code_to_cat[item["code"]] = {
        "name": item.get("name", ""),
        "category": item.get("category", ""),
    }

# 筛选10年+(2500天+)的
candidates = []
for f in os.listdir(DATA_DIR):
    if not f.endswith(".json"):
        continue
    code = f.replace(".json", "")
    raw = json.load(open(os.path.join(DATA_DIR, f), "r", encoding="utf-8"))
    r = raw["records"] if isinstance(raw, dict) else raw
    n = len(r)
    if n < 2500:
        continue
    info = code_to_cat.get(code, {})
    name = info.get("name", "?")
    cat = info.get("category", "?")
    first, last = r[0]["date"], r[-1]["date"]
    candidates.append((code, name, cat, n, first, last))

# 按类别分组
cats = {}
for c, n, cat, cnt, f, l in candidates:
    cats.setdefault(cat, []).append((c, n, cat, cnt, f, l))

print(f"共 {len(candidates)} 只ETF满足10年+(2500+条)\n")
print(f"{'类别':<15} {'数量':>4}  代表品种")
print("-" * 60)
for cat, items in sorted(cats.items()):
    names = ", ".join([f"{c[0]}({c[1][:8]})" for c in items[:5]])
    if len(items) > 5:
        names += f" ... +{len(items)-5}"
    print(f"{cat:<15} {len(items):>4}  {names}")
