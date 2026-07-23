import json
with open("D:\\QClaw_Trading\\etf_pool_cn.json", encoding="utf-8") as f:
    data = json.load(f)

# Build dict from list - keys are Chinese, use positional access
pool = {}
for e in data:
    vals = list(e.values())
    code = vals[1]  # second field is code
    name = vals[2]  # third is name
    cat = vals[3]   # fourth is category
    pool[code] = {"name": name, "category": cat}

wanted = [
    ("510050", "上证50"), ("510300", "沪深300"), ("510500", "中证500"),
    ("512100", "中证1000"), ("159915", "创业板指"), ("159949", "创业板50"),
    ("588000", "科创50"), ("159902", "中小100"),
    ("513500", "标普500"), ("159941", "纳指ETF"),
    ("518880", "黄金ETF"),
]

print("FOUND in pool:")
for c, n in wanted:
    if c in pool:
        print(f"  {c} {n:<8}  cat={pool[c]['category']}  {pool[c]['name']}")
    else:
        print(f"  {c} {n:<8}  NOT IN POOL")
