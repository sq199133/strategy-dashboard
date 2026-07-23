# -*- coding: utf-8 -*-
"""补齐61只快照未覆盖的ETF到2026-07-14"""
import json, re, urllib.request, time
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}

# All 159xxx codes from pool
MISSING_CODES = [
    "159792","159852","159561","159869","159745","159698","159107","159572",
    "159108","159328","159725","159918","159822","159980","159985","159870",
    "159995","159819","159949","159851","159667","159638","159141","159607",
    "159529","159326","159206","159928","159755","159611","159363","159865",
    "159766","159625","159623","159209","159732","159905","159259","159387",
    "159837","159758","159996","159939","159207","159378","159628","159902",
    "159773","159761","159743","159786","159678","159666","159804","159872",
    "159617","159620","159981","159687","159399",
]

def sina_kline_last(code, n=5):
    mkt = "sz" if code.startswith("159") else "sh"
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&datalen={n}")
    req = urllib.request.Request(url, headers=UA)
    resp = urllib.request.urlopen(req, timeout=20)
    data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return [(r["day"].split()[0], float(r["open"]), float(r["high"]),
             float(r["low"]), float(r["close"]), int(float(r.get("volume", 0))))
            for r in data] if data else []

def append_one(code, kline_data, today):
    hf = HISTORY / f"{code}.json"
    if not hf.exists():
        return False
    with open(hf, encoding="utf-8") as f:
        obj = json.load(f)
    records = obj.get("records", [])
    last_date = records[-1]["date"] if records else "1900-01-01"

    today_rec = next((r for r in kline_data if r[0] == today), None)
    if not today_rec:
        return False
    if last_date == today:
        return False

    vol_key = "vol"
    with open(hf, encoding="utf-8") as f:
        txt = f.read()
    if '"volume":' in txt:
        vol_key = "volume"

    new_rec = {
        "date": today_rec[0], "open": round(today_rec[1], 4),
        "high": round(today_rec[2], 4), "low": round(today_rec[3], 4),
        "close": round(today_rec[4], 4), vol_key: today_rec[5],
        "amount": 0, "chg": 0.0,
    }
    records.append(new_rec)
    obj["records"] = records
    obj["update"] = today
    with open(hf, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    return True

def main():
    # Detect today from kline
    probe = sina_kline_last("510500", n=3)
    today = probe[-1][0] if probe else "2026-07-14"
    print(f"Today: {today}, codes: {len(MISSING_CODES)}")

    updated = 0
    for code in MISSING_CODES:
        try:
            klines = sina_kline_last(code, n=5)
            if klines:
                ok = append_one(code, klines, today)
                if ok:
                    updated += 1
                    r = klines[-1]
                    pct = (r[4] / r[1] - 1) * 100 if r[1] else 0
                    print(f"  + {code} {r[0]} C={r[4]:.4f} ({pct:+.2f}%)")
        except Exception as e:
            print(f"  ERR {code}: {e}")
        time.sleep(0.12)

    print(f"\nPatched: {updated}/{len(MISSING_CODES)}")

if __name__ == "__main__":
    main()
