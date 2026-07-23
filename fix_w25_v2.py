"""Fix: use isocalendar() for correct ISO week number, not date string split.
Also handle the holiday-gap closing correctly.
"""
import json, datetime
from pathlib import Path

HIST = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

pool_data = json.loads(POOL.read_text(encoding="utf-8"))
pool = pool_data["data"] if isinstance(pool_data, dict) and "data" in pool_data else pool_data
etf_map = {e["code"]: e for e in pool}

def read_json_safe(fp):
    raw = fp.read_bytes()
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            return json.loads(raw.decode(enc))
        except:
            continue
    return None

def write_json_safe(fp, data):
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    fp.write_text(text, encoding="utf-8")

def iso_week_label(dt):
    """Return ISO year-week label like '2026-W25'"""
    yr, wk, _ = dt.isocalendar()
    return f"{yr}-W{wk:02d}"

def daily_to_weekly(daily_records):
    """Aggregate daily → weekly.
    
    Week closes on:
    1. Friday (weekday == 4) — normal end
    2. Holiday/weekend gap >= 2 calendar days — close BEFORE the gap
       (anchor = last day before gap)
    3. Last record — always close
    """
    if not daily_records:
        return []

    weekly = []
    week_data = []
    prev_dt = None

    for i, r in enumerate(daily_records):
        if not (isinstance(r, dict) and "date" in r):
            continue
        dt = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()

        # Holiday gap: prev day + gap >= 2 means we crossed a break
        # Close current week BEFORE adding the new record
        if prev_dt is not None:
            gap = (dt - prev_dt).days
            if gap >= 2 and week_data:
                anchor = daily_records[i - 1] if i > 0 else r
                _close_week(week_data, weekly, anchor)

        week_data.append(r)
        prev_dt = dt

        if dt.weekday() == 4:
            _close_week(week_data, weekly, r)
        elif i == len(daily_records) - 1 and week_data:
            _close_week(week_data, weekly, r)

    return weekly


def _close_week(week_data, weekly, anchor_record):
    """Append one weekly bar to weekly list."""
    dt = datetime.datetime.strptime(anchor_record["date"], "%Y-%m-%d").date()
    close_p = float(anchor_record["close"])
    open_p = float(week_data[0].get("open", close_p))
    high_p = float(max(x.get("high", close_p) for x in week_data))
    low_p = float(min(x.get("low", close_p) for x in week_data))
    vol = sum(float(x.get("vol", 0)) for x in week_data)

    rec = {
        "w": iso_week_label(dt),   # ← FIX: use isocalendar(), not split
        "date": anchor_record["date"],
        "close": round(close_p, 4),
    }
    if "open" in week_data[0]:
        rec["open"] = round(open_p, 4)
    if "high" in week_data[0]:
        rec["high"] = round(high_p, 4)
    if "low" in week_data[0]:
        rec["low"] = round(low_p, 4)
    if "vol" in week_data[0] or any("vol" in x for x in week_data):
        rec["vol"] = round(vol, 0)

    weekly.append(rec)


# === Regenerate all 195 weekly files ===
print("Regenerating weekly files for all 195 ETFs...")
updated = 0
skipped = 0

for item in pool:
    code = item["code"]
    hist_fp = HIST / f"{code}.json"
    v2_fp = LONG_V2 / f"{code}.json"

    hist = read_json_safe(hist_fp)
    if not hist:
        print(f"  {code}: HIST MISSING")
        continue

    recs = hist.get("records", hist) if isinstance(hist, dict) else hist
    if not recs:
        skipped += 1
        continue

    weekly = daily_to_weekly(recs)
    name = etf_map.get(code, {}).get("name", "")
    data = {
        "code": code,
        "name": name,
        "update": weekly[-1]["date"] if weekly else "",
        "records": weekly
    }
    write_json_safe(v2_fp, data)

    # Check W25
    w_labels = [w["w"] for w in weekly]
    w25_exists = "2026-W25" in w_labels
    marker = " [W25]" if w25_exists else ""
    last_w = weekly[-1]["w"] if weekly else "N/A"
    print(f"  {code}{marker}: last={last_w} ({len(weekly)} weeks)")
    updated += 1

print(f"\nDone: {updated} updated, {skipped} skipped")
