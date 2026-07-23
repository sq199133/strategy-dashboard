# -*- coding: utf-8 -*-
"""批量快照更新 v2: GB18030解码 + 完整196只批量"""
import json, re, time, urllib.request
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
POOL_FILE = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "http://finance.sina.com.cn"}

def load_pool_codes():
    with open(POOL_FILE, encoding="utf-8") as f:
        obj = json.load(f)
    codes = [item["code"] for item in obj["data"]]
    # Add factor ETFs not in pool
    for fc in ["512890", "515910", "512750", "159399"]:
        if fc not in codes:
            codes.append(fc)
    return codes

def build_sina_url(codes):
    """构建 Sina hq 批量 URL"""
    parts = []
    for c in codes:
        if c.startswith(("sh", "sz", "hk", "us")):
            parts.append(c)
        elif c[0] == "5" or re.match(r"^1[15]\d{4}$", c):  # 5xx / 11x / 15x = 上海
            parts.append(f"sh{c}")
        else:  # sz
            parts.append(f"sz{c}")
    return "http://hq.sinajs.cn/list=" + ",".join(parts)

def parse_sina_spot(raw_text):
    """解析 Sina 批量快照，返回 {code: spot_dict}"""
    results = {}
    # Non-greedy [^\"]+ stops at first closing quote
    for m in re.finditer(r'hq_str_(sh|sz)(\w+)="([^"]+)"', raw_text):
        code = m.group(2)
        fields_str = m.group(3)
        fields = [f.strip() for f in fields_str.split(",")]
        if len(fields) < 9:
            continue
        try:
            # 字段结构: [0]name [1]open [2]prev [3]low [4]high [5]close [6-11]bid/ask [12]vol [13]amount [last-3]time [last-2]status [last-1]suffix
            # 日期在 [last-4]，时间在 [last-3]
            # 试探: 先找倒数第4个是日期格式的字段
            date_str = None
            for fi in range(-6, -1):
                if re.match(r"\d{4}-\d{2}-\d{2}", fields[fi]):
                    date_str = fields[fi]
                    break
            if not date_str:
                continue
            # Sina快照字段顺序: [0]name [1]open [2]prev [3]low [4]high [5]close [6-?]bid/ask [12]vol [13]amount
            # 注意: [3]=low, [4]=high (与标准open/high/low/close不同)
            try:
                vol_raw = fields[12] if len(fields) > 12 else fields[7]
                amt_raw = fields[13] if len(fields) > 13 else fields[8]
                results[code] = {
                    "date":   date_str,
                    "open":   float(fields[1]),
                    "prev":   float(fields[2]),
                    "low":    float(fields[3]),
                    "high":   float(fields[4]),
                    "close":  float(fields[5]),
                    "vol":    int(float(vol_raw)) if vol_raw else 0,
                    "amount": float(amt_raw) if amt_raw else 0.0,
                }
            except (ValueError, IndexError):
                continue
        except (ValueError, IndexError):
            continue
    return results

def detect_vol_key(file_path):
    """判断文件中用的是 vol 还是 volume"""
    with open(file_path, encoding="utf-8") as f:
        txt = f.read()
    return "vol" if '"vol":' in txt else "volume"

def append_today(code, spot, hist_file):
    vol_key = detect_vol_key(hist_file)
    today = spot["date"]

    with open(hist_file, encoding="utf-8") as f:
        obj = json.load(f)

    records = obj.get("records", [])
    last_date = records[-1]["date"] if records else "1900-01-01"

    if last_date == today:
        return False  # already up to date

    new_rec = {
        "date":   today,
        "open":   round(spot["open"], 4),
        "high":   round(spot["high"], 4),
        "low":    round(spot["low"], 4),
        "close":  round(spot["close"], 4),
        vol_key:  spot["vol"],
        "amount": 0,
        "chg":    0.0,
    }
    records.append(new_rec)
    obj["records"] = records
    obj["update"] = today

    with open(hist_file, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    return True

def main():
    codes = load_pool_codes()
    print(f"Total ETFs: {len(codes)}")

    # Sina URL char limit ~2000, 196 codes * ~8 = ~1568 chars → OK in one batch
    url = build_sina_url(codes)
    print(f"URL length: {len(url)}")

    req = urllib.request.Request(url, headers=UA)
    resp = urllib.request.urlopen(req, timeout=30)
    raw_bytes = resp.read()
    # Use charset from header, fallback to GB18030
    charset = resp.headers.get_content_charset() or "GB18030"
    raw_text = raw_bytes.decode(charset, errors="replace")
    print(f"Response: {len(raw_bytes)} bytes, decoded as {charset}, text len={len(raw_text)}")

    spot_data = parse_sina_spot(raw_text)
    print(f"Parsed snapshots: {len(spot_data)}")

    updated = skipped = errors = 0
    for code in codes:
        if code not in spot_data:
            continue  # suspended or not found
        hf = HISTORY / f"{code}.json"
        if not hf.exists():
            errors += 1; continue
        try:
            ok = append_today(code, spot_data[code], hf)
            if ok:
                updated += 1
                s = spot_data[code]
                pct = (s["close"] / s["prev"] - 1) * 100 if s["prev"] else 0
                print(f"  + {code} {s['date']} C={s['close']:.4f} V={s['vol']:,} ({pct:+.2f}%)")
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERR {code}: {e}")
            errors += 1

    print(f"\nDone — updated={updated} skipped={skipped} errors={errors}")

if __name__ == "__main__":
    main()
