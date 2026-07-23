import json, os

codes = {
    "510050": "上证50", "510300": "沪深300", "510500": "中证500",
    "512100": "中证1000", "159531": "中证2000", "563300": "中证2000-2",
    "159915": "创业板指", "159949": "创业板50", "588000": "科创50",
    "513500": "标普500", "513100": "纳指ETF", "513300": "未知(疑标普)",
    "513400": "道琼斯ETF",
    "518880": "黄金ETF", "162411": "华宝油气(原油)", "160416": "石油基金",
    "159981": "能源化工ETF", "159985": "豆粕ETF", "501018": "南方原油",
    "161129": "原油基金",
}

results = []
for c, n in sorted(codes.items()):
    f = "D:\\QClaw_Trading\\data\\history\\%s.json" % c
    if os.path.exists(f):
        with open(f,"r",encoding="utf-8") as fh:
            d = json.load(fh)
        recs = len(d.get("records",[]))
        dname = d.get("name","")
        first = d["records"][0]["date"] if d.get("records") else "-"
        last = d["records"][-1]["date"] if d.get("records") else "-"
        results.append((c, n, dname, recs, first, last))
    else:
        results.append((c, n, "", 0, "-", "-"))

# Save to file to avoid GBK issues
with open("D:\\QClaw_Trading\\RSRS\\etf_summary.txt","w",encoding="utf-8") as f:
    f.write("code     label          data_name     records  first_date  last_date\n")
    f.write("-"*80+"\n")
    for c, n, dn, recs, fst, lst in results:
        dn = dn[:20] if dn else "-"
        f.write("%s %-14s %-14s %7d  %s - %s\n" % (c, n, dn, recs, fst, lst))

print("Saved to D:\\QClaw_Trading\\RSRS\\etf_summary.txt")
