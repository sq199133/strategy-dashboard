# -*- coding: utf-8 -*-
"""补全因子ETF数据: 下载Sina原始K线 -> 检测拆分 -> 前复权 -> 保存为池格式"""
import json, urllib.request, time, sys

HISTORY = r"D:\QClaw_Trading\data\history"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 正确因子ETF清单 (代码, 简称, 因子标签)
TARGETS = [
    ("512890", "红利低波ETF", "low_vol"),
    ("515910", "质量ETF",     "quality"),
    ("512750", "基本面50ETF", "fundamental"),
    ("159399", "现金流ETF",   "cashflow"),
]

def sina_kline(code):
    mkt = "sh" if code[0] == "5" else "sz"
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&datalen=5000")
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    data = json.loads(raw)
    recs = []
    for r in data:
        recs.append({
            "date": str(r["day"]).split()[0],
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "vol": int(float(r.get("volume", 0))),
        })
    recs.sort(key=lambda x: x["date"])
    return recs

def detect_splits(recs):
    """返回 [(date, factor, prev_close_raw, new_close_raw), ...] 晚->早排序"""
    splits = []
    for i in range(1, len(recs)):
        prev = recs[i-1]["close"]
        cur = recs[i]["close"]
        if prev <= 0:
            continue
        ratio = cur / prev
        # ETF单日跌超25%几乎必为拆分(正常最大单日跌幅<10%)
        if ratio <= 0.75:
            splits.append((recs[i]["date"], round(ratio, 6), prev, cur))
    # 晚->早
    splits.sort(key=lambda x: x[0], reverse=True)
    return splits

def forward_adjust(recs, splits):
    out = [dict(r) for r in recs]
    for (d, factor, pcr, ncr) in splits:
        for r in out:
            if r["date"] < d:
                r["open"]  *= factor
                r["high"]  *= factor
                r["low"]   *= factor
                r["close"] *= factor
    return out

def save(code, name, recs, splits):
    records = []
    for r in recs:
        records.append({
            "date": r["date"], "open": round(r["open"],4),
            "close": round(r["close"],4), "high": round(r["high"],4),
            "low": round(r["low"],4), "vol": r["vol"],
            "amount": 0, "chg": 0.0,
        })
    adjustments = [{"date": d, "factor": f, "ret_pct": round((f-1)*100,2),
                    "prev_close_raw": pcr, "new_close_raw": ncr} for (d,f,pcr,ncr) in splits]
    obj = {"code": code, "name": name, "records": records,
           "adjustments": adjustments, "update": records[-1]["date"]}
    path = f"{HISTORY}\\{code}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return path

def main():
    summary = []
    for code, name, tag in TARGETS:
        try:
            recs = sina_kline(code)
            splits = detect_splits(recs)
            adj = forward_adjust(recs, splits)
            path = save(code, name, adj, splits)
            summary.append((code, name, tag, len(adj), adj[-1]["date"],
                            len(splits), [s[0] for s in splits], path))
            print(f"[OK] {code} {name} [{tag}] records={len(adj)} last={adj[-1]['date']} splits={len(splits)} {[s[0] for s in splits]}")
        except Exception as e:
            print(f"[FAIL] {code} {name}: {e}")
        time.sleep(0.3)
    print("\n=== SUMMARY ===")
    for s in summary:
        print(s[0], s[1], s[2], "n=", s[3], "last=", s[4], "splits=", s[5], s[6])

if __name__ == "__main__":
    main()
