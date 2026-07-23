import json, os, glob

# Pool
with open("D:\\QClaw_Trading\\etf_pool_cn.json", encoding="utf-8") as f:
    plist = json.load(f)
pool = {}
for e in plist:
    v = list(e.values())
    pool[v[1]] = {"name": v[2], "cat": v[3]}

# Data files
hist = set(os.path.splitext(os.path.basename(f))[0] for f in glob.glob("D:\\QClaw_Trading\\data\\history\\*.csv"))

wanted = [
    ("510050","上证50"),("510300","沪深300"),("510500","中证500"),
    ("512100","中证1000"), ("159915","创业板指"),("159949","创业板50"),
    ("588000","科创50"),
    ("513500","标普500"),("159941","纳指ETF"),
    ("518880","黄金ETF"),
]

print("code    name      pool data category")
print("-"*50)
for c, n in wanted:
    ip = c in pool
    id_ = c in hist
    pc = pool[c]["cat"] if ip else "-"
    pn = pool[c]["name"] if ip else "-"
    print(f"{c} {n:<8} {int(ip)} {int(id_)} {pc} {pn[:24]}")

print()
print("Searching for zhongzheng 2000...")
for c, e in sorted(pool.items()):
    nm = e["name"]
    if "2000" in nm or "2000" in c:
        print(f"  {c} {e['name']} ({e['cat']})")
    if "中证2000" in nm:
        print(f"  EXACT: {c} {nm}")

# Also check 琼 and 纳斯达克
print()
for c, e in sorted(pool.items()):
    nm = e["name"]
    if "道" in nm or "琼" in nm or "纳" in nm or "纳斯达" in nm:
        print(f"  {c} {e['name']} ({e['cat']})")
