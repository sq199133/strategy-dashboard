# -*- coding: utf-8 -*-
"""批量快照更新：Sina实时行情 -> 追加到各ETF日线文件"""
import json, re, time, urllib.request, sys
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
POOL_FILE = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "http://finance.sina.com.cn"}

def load_pool():
    with open(POOL_FILE, encoding="utf-8") as f:
        obj = json.load(f)
    return [item["code"] for item in obj["data"]]

def sina_spot_batch(codes):
    """Sina实时快照批量接口，返回 {code: {date,open,high,low,close,vol,amount}}"""
    parts = []
    for c in codes:
        prefix = "sh" if c[0] == "5" or c[0] == "1" and c[:3] in ("110","120","128","500","880") else "sz"
        parts.append(f"{prefix}{c}")
    url = "http://hq.sinajs.cn/list=" + ",".join(parts)
    req = urllib.request.Request(url, headers=UA)
    resp = urllib.request.urlopen(req, timeout=30)
    raw = resp.read().decode("gbk", errors="replace")
    results = {}
    # Parse var hq_str_xxCODE="..." lines
    for m in re.finditer(r'hq_str_(sh|sz)(\w+)=', raw):
        code = m.group(2)
        pos = m.end()
        # Find end of quoted string
        end_q = raw.index('"', pos)
        fields_str = raw[pos+1:end_q]
        fields = [f.strip() for f in fields_str.split(",")]
        if len(fields) < 10:
            continue
        try:
            date_str = fields[-3]  # e.g. "2026-07-13"
            time_str = fields[-2]
            if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                continue
            results[code] = {
                "date": date_str,
                "time": time_str,
                "open":  float(fields[1]),
                "prev":  float(fields[2]),
                "high":  float(fields[3]),
                "low":   float(fields[4]),
                "close": float(fields[5]),
                "vol":   int(float(fields[7])) if fields[7] else 0,
                "amount": float(fields[8]) if fields[8] else 0.0,
            }
        except (ValueError, IndexError):
            continue
    return results

def append_today(code, spot, hist_file):
    """将今日快照追加到历史文件（若日期不重复）"""
    with open(hist_file, encoding="utf-8") as f:
        obj = json.load(f)

    # 找最后一条真实OHLCV记录
    records = obj.get("records", [])
    last_date = records[-1]["date"] if records else "1900-01-01"

    today = spot["date"]
    if last_date == today:
        print(f"  SKIP {code}: already has {today}")
        return False

    # 检查 vol 字段名（159901/512690用volume，其余用vol）
    vol_key = "vol"
    with open(hist_file, encoding="utf-8") as f:
        content = f.read()
    if '"volume":' in content:
        vol_key = "volume"

    new_rec = {
        "date":   today,
        "open":   round(spot["open"], 4),
        "high":   round(spot["high"], 4),
        "low":    round(spot["low"], 4),
        "close":  round(spot["close"], 4),
        "vol":    spot["vol"],
        "amount": 0,
        "chg":    0.0,
    }
    if vol_key == "volume":
        new_rec["volume"] = new_rec.pop("vol")

    records.append(new_rec)
    obj["records"] = records
    obj["update"] = today

    with open(hist_file, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    prev_close = records[-2]["close"] if len(records) >= 2 else None
    pct = (spot["close"] / spot["prev"] - 1) * 100 if spot["prev"] else 0
    print(f"  OK   {code} {today} C={spot['close']:.4f} Δ={pct:+.2f}%")
    return True

def main():
    print("Loading pool...")
    codes = load_pool()
    print(f"Pool: {len(codes)} ETFs")

    # Also add the 4 new factor ETFs not in pool
    factor_codes = ["512890", "515910", "512750", "159399"]
    for fc in factor_codes:
        if fc not in codes:
            codes.append(fc)
    print(f"Total to update: {len(codes)} (pool + factor)")

    print("Fetching Sina snapshot...")
    spot_data = sina_spot_batch(codes)
    print(f"Sina returned {len(spot_data)} snapshots")

    updated = 0
    skipped = 0
    errors = 0
    for code in codes:
        if code not in spot_data:
            print(f"  MISS {code}: no snapshot (may be suspended)")
            continue
        hist_file = HISTORY / f"{code}.json"
        if not hist_file.exists():
            print(f"  NOFILE {code}")
            errors += 1
            continue
        try:
            ok = append_today(code, spot_data[code], hist_file)
            if ok: updated += 1
            else: skipped += 1
        except Exception as e:
            print(f"  ERR  {code}: {e}")
            errors += 1

    print(f"\nDone: updated={updated} skipped={skipped} errors={errors}")

if __name__ == "__main__":
    main()
