import json, os

codes = ["162411","159981","159985","501018","161129","160416",
         "159531","563300","159530","513100","513300", "513400"]
for c in codes:
    f = "D:\\QClaw_Trading\\data\\history\\%s.json" % c
    if os.path.exists(f):
        with open(f,"r",encoding="utf-8") as fh:
            data = json.load(fh)
        recs = len(data.get("records",[]))
        first = data["records"][0]["date"] if data.get("records") else "none"
        last = data["records"][-1]["date"] if data.get("records") else "none"
        print("%s: recs=%d  %s - %s" % (c, recs, first, last))
    else:
        print("%s: NO DATA FILE" % c)
