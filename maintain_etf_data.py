#!/usr/bin/env python3
"""
ETF 数据维护脚本 — 主入口
职责：检查数据完整性、补充/更新、修复格式、报告状态
      同时维护日线(history/) 和 周线(history_long_v2/)
      支持ETF池 + 指数池统一维护

用法：
  python maintain_etf_data.py check              # 仅检查（含交易日校验）
  python maintain_etf_data.py update             # 补充短数据
  python maintain_etf_data.py incremental        # 增量更新ETF池
  python maintain_etf_data.py incremental --force # 强制全量增量更新
  python maintain_etf_data.py sync-weekly        # 从日线同步生成周线
  python maintain_etf_data.py cleanup            # 列出非池标文件
  python maintain_etf_data.py update-indices     # 更新指数池（A股+海外+商品）
  python maintain_etf_data.py update-all         # 一键更新：ETF池 + 指数池

交易日规则：
  - weekday 5=Sat, 6=Sun → 非交易日
  - HOLIDAYS[year] → 非交易日（节假日）
  - COMPENSATORY_DAYS[year] → 交易日（调休上班日）
"""
import json, sys, time, random, requests
from datetime import datetime, date
from pathlib import Path

# === Paths ===
HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
README = HISTORY.parent / "README.md"

# === Config ===
MIN_RECORDS = 80  # 最少可接受记录数（日线）
STALE_DAYS = 30   # 超过此天数未更新视为过期
API_DELAY = (0.3, 1.0)  # 请求间隔（秒）

# === A股交易日历 ===
# 用途：数据校验 + 更新时过滤非法日期
# 注意：调休上班日（周末变交易日）在下方 COMPENSATORY_DAYS 中声明
# 注意：每年需更新节假日数据

HOLIDAYS = {
    2024: {
        date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 11),
        date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14), date(2024, 2, 15),
        date(2024, 2, 16), date(2024, 2, 17),
        date(2024, 4, 4), date(2024, 4, 5), date(2024, 4, 6),
        date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3), date(2024, 5, 4), date(2024, 5, 5),
        date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 12),
        date(2024, 9, 15), date(2024, 9, 16), date(2024, 9, 17),
        date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3), date(2024, 10, 4),
        date(2024, 10, 5), date(2024, 10, 6), date(2024, 10, 7),
    },
    2025: {
        date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
        date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2), date(2025, 2, 3), date(2025, 2, 4),
        date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),
        date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3), date(2025, 5, 4), date(2025, 5, 5),
        date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 2),
        date(2025, 9, 15), date(2025, 9, 16), date(2025, 9, 17),
        date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3), date(2025, 10, 4),
        date(2025, 10, 5), date(2025, 10, 6), date(2025, 10, 7),
    },
    2026: {
        date(2026, 1, 1),
        date(2026, 2, 15), date(2026, 2, 16), date(2026, 2, 17),
        date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21),
        date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),
        date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3), date(2026, 5, 4), date(2026, 5, 5),
        date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),
        date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4),
        date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8),
    },
    2027: {
        date(2027, 1, 1), date(2027, 1, 2), date(2027, 1, 3),
        date(2027, 2, 7), date(2027, 2, 8), date(2027, 2, 9), date(2027, 2, 10),
        date(2027, 2, 11), date(2027, 2, 12), date(2027, 2, 13), date(2027, 2, 14),
        date(2027, 4, 5), date(2027, 4, 6),
        date(2027, 5, 3), date(2027, 5, 4), date(2027, 5, 5),
        date(2027, 6, 26), date(2027, 6, 27), date(2027, 6, 28),
        date(2027, 9, 26), date(2027, 9, 27), date(2027, 9, 28),
        date(2027, 10, 1), date(2027, 10, 2), date(2027, 10, 3), date(2027, 10, 4),
        date(2027, 10, 5), date(2027, 10, 6), date(2027, 10, 7),
    },
}

# 调休上班日（周末变交易日）：weekday 5=Sat, 6=Sun
COMPENSATORY_DAYS = {
    2024: {date(2024, 2, 4), date(2024, 2, 18), date(2024, 5, 11), date(2024, 9, 29), date(2024, 10, 12)},
    2025: {date(2025, 1, 26), date(2025, 2, 8), date(2025, 4, 27), date(2025, 8, 31), date(2025, 10, 11)},
    2026: {date(2026, 2, 22), date(2026, 2, 28), date(2026, 4, 26), date(2026, 9, 27), date(2026, 10, 10)},
    2027: {date(2027, 2, 21), date(2027, 2, 28), date(2027, 4, 4), date(2027, 8, 30), date(2027, 9, 26)},
}


def is_trading_day(dt: date) -> bool:
    """判断 dt 是否为 A 股交易日。
    
    规则：
    - weekday >= 5（周六/周日）→ 非交易日
    - 在 HOLIDAYS[year] 中 → 非交易日
    - 在 COMPENSATORY_DAYS[year] 中 → 交易日（调休上班）
    """
    yr = dt.year
    if dt.weekday() >= 5:  # 周六(5)或周日(6)
        # 调休上班日例外
        if yr in COMPENSATORY_DAYS and dt in COMPENSATORY_DAYS[yr]:
            return True
        return False
    if yr in HOLIDAYS and dt in HOLIDAYS[yr]:
        return False
    return True


def filter_trading_days(records: list) -> list:
    """过滤掉所有非交易日的记录（周末/节假日）。返回干净的记录列表。"""
    return [r for r in records if is_trading_day(date.fromisoformat(r["date"]))]


# === Helpers ===

def load_pool():
    return json.loads(POOL.read_text(encoding="utf-8"))["data"]

def read_json_safe(fp):
    """Auto-detect encoding: try UTF-8 first, fallback to GBK."""
    raw = fp.read_bytes()
    if len(raw) == 0:
        return None
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("gbk", errors="replace"))

def write_json_safe(fp, data):
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    fp.write_text(text, encoding="utf-8")

def get_records(data):
    if isinstance(data, dict):
        return data.get("records", [])
    return data if isinstance(data, list) else []

def code_market(code):
    c = str(code).strip()
    if c.startswith(("6", "5")):
        return "sh"
    if c.startswith(("0", "3", "1", "2")):
        return "sz"
    return "sz"

# === Data Download ===

def download_via_tencent(code, datalen=2000):
    """Download using Tencent ifzq KLine API (跨境/A股全深度).
    
    默认 2000 条 ≈ 8 年 (2018~2026)，腾讯极限 2000。
    Sina 默认 1500 条 ≈ 6 年。
    """
    import urllib.request, json
    market = code_market(code)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{datalen},"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("code") != 0:
            return None
        rows = j.get("data", {}).get(f"{market}{code}", {}).get("day")
        if not rows:
            return None
        records = []
        for r in rows:
            records.append({
                "date": r[0],
                "open": float(r[1]),
                "close": float(r[2]),
                "high": float(r[3]),
                "low": float(r[4]),
                "vol": int(float(r[5])),
                "amount": 0,
                "chg": 0.0
            })
        records.sort(key=lambda r: r["date"])
        return records
    except Exception:
        return None


def download_via_sina(code):
    """Download using Sina API (~1500 records = ~6 years)."""
    market = code_market(code)
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=1500")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or not r.text.strip() or len(r.text) < 10:
            return None
        data = r.json()
        if not data:
            return None
        records = []
        for row in data:
            day = row["day"].split()[0]
            records.append({
                "date": day,
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "vol": int(float(row.get("volume", 0))),
                "amount": int(float(row.get("amount", 0))),
                "chg": 0.0
            })
        # 交易日过滤：去除周末/节假日记录
        clean = filter_trading_days(records)
        removed = len(records) - len(clean)
        if removed > 0:
            bad = [r["date"] for r in records if not is_trading_day(date.fromisoformat(r["date"]))]
            print(f"  (过滤{removed}条非交易日: {bad[:5]}{'...' if removed > 5 else ''})", end="")
        clean.sort(key=lambda r: r["date"])
        return clean
    except Exception:
        return None

# === Weekly Aggregation ===

def daily_to_weekly(daily_records):
    """Aggregate daily → weekly (Fri-based).

    Week closes on Friday (weekday==4) only.
    Last non-Friday record: leave week open (wait for next Friday).
    Holiday gaps within week: no special handling — week accumulates until Friday.
    """
    if not daily_records:
        return []
    weekly = []
    week_data = []

    for i, r in enumerate(daily_records):
        if not (isinstance(r, dict) and "date" in r):
            continue
        dt = datetime.strptime(r["date"], "%Y-%m-%d").date()

        week_data.append(r)

        if dt.weekday() == 4:
            # Friday: close the week
            _close_week(week_data, weekly, r)
            week_data = []

    return weekly


def _close_week(week_data, weekly, anchor_record):
    """Append one weekly OHLCV bar using anchor_record as the close date."""
    dt = datetime.strptime(anchor_record["date"], "%Y-%m-%d").date()
    iso_yr, iso_wk, _ = dt.isocalendar()
    close_p = float(anchor_record["close"])
    open_p = float(week_data[0].get("open", close_p))
    high_p = float(max(x.get("high", close_p) for x in week_data))
    low_p = float(min(x.get("low", close_p) for x in week_data))
    vol = sum(float(x.get("vol", 0)) for x in week_data)
    rec = {"w": f"{iso_yr}-W{iso_wk:02d}", "date": anchor_record["date"], "close": round(close_p, 4)}
    if "open" in week_data[0]:
        rec["open"] = round(open_p, 4)
    if "high" in week_data[0]:
        rec["high"] = round(high_p, 4)
    if "low" in week_data[0]:
        rec["low"] = round(low_p, 4)
    if "vol" in week_data[0] or any("vol" in x for x in week_data):
        rec["vol"] = round(vol, 0)
    weekly.append(rec)

def sync_weekly_for_code(code, name=""):
    """Generate weekly data from daily for one ETF. Returns (weekly_count, changed)."""
    hist_fp = HISTORY / f"{code}.json"
    v2_fp = LONG_V2 / f"{code}.json"
    
    if not hist_fp.exists():
        return (0, False)
    
    hist_raw = read_json_safe(hist_fp)
    if hist_raw is None:
        return (0, False)
    
    daily_records = get_records(hist_raw)
    if not daily_records:
        return (0, False)
    
    weekly = daily_to_weekly(daily_records)
    if not weekly:
        return (0, False)

    # Remove duplicate w-labels (keep last = most recent data)
    seen, clean = set(), []
    for w in reversed(weekly):
        label = w["w"]
        if label not in seen:
            seen.add(label)
            clean.insert(0, w)
    weekly = clean

    existing = None
    changed = True
    if v2_fp.exists():
        old_v2 = read_json_safe(v2_fp)
        if old_v2 is not None:
            old_recs = get_records(old_v2)
            if len(old_recs) == len(weekly) and old_recs and weekly:
                if old_recs[-1].get("date") == weekly[-1].get("date"):
                    changed = False

    if changed:
        write_json_safe(v2_fp, {
            "code": code, "name": name,
            "update": weekly[-1]["date"],
            "records": weekly
        })

    return (len(weekly), changed)

# === Commands ===

def cmd_check(verbose=False):
    
    pool = load_pool()
    today = date.today()
    issues = []
    total_records = 0
    min_rec, max_rec = 999999, 0
    min_code = max_code = ""
    weekly_ok = 0
    weekly_total = 0
    
    for e in pool:
        code = e["code"]
        fp = HISTORY / f"{code}.json"
        
        if not fp.exists():
            issues.append(("MISS", code, "日线文件不存在"))
            continue
        
        raw = read_json_safe(fp)
        if raw is None:
            issues.append(("ERR", code, "JSON解析失败"))
            continue
        
        records = get_records(raw)
        n = len(records)
        total_records += n
        
        if n < min_rec:
            min_rec, min_code = n, code
        if n > max_rec:
            max_rec, max_code = n, code
        
        if n < MIN_RECORDS:
            issues.append(("SHORT", code, f"仅{n}条日线"))
            continue
        
        try:
            last_date = records[-1]["date"]
            dt_data = datetime.strptime(last_date, "%Y-%m-%d").date()
            if (today - dt_data).days > STALE_DAYS:
                issues.append(("STALE", code, f"最后数据{last_date}，已{(today-dt_data).days}天"))
            # 交易日历校验：最后日期不能是周末或节假日
            if not is_trading_day(dt_data):
                issues.append(("NON_TD", code, f"最后日期{last_date}({dt_data.strftime('%A')})不是交易日！"))
        except:
            pass
        
        # Check weekly
        v2_fp = LONG_V2 / f"{code}.json"
        if v2_fp.exists():
            v2_raw = read_json_safe(v2_fp)
            v2_recs = get_records(v2_raw) if v2_raw else []
            weekly_total += len(v2_recs)
            if len(v2_recs) >= 4:
                weekly_ok += 1
            else:
                issues.append(("W_SHORT", code, f"仅{len(v2_recs)}条周线"))
        else:
            issues.append(("W_MISS", code, "周线文件缺失"))
    
    total = len(pool)
    missing = sum(1 for i in issues if i[0] == "MISS")
    short = sum(1 for i in issues if i[0] == "SHORT")
    stale = sum(1 for i in issues if i[0] == "STALE")
    parse_err = sum(1 for i in issues if i[0] == "ERR")
    w_miss = sum(1 for i in issues if i[0] == "W_MISS")
    w_short = sum(1 for i in issues if i[0] == "W_SHORT")
    clean = total - missing - short - parse_err
    
    print(f"{'='*50}")
    print(f"ETF 数据健康检查 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'='*50}")
    print(f"  【日线】")
    print(f"   标的池:      {total}")
    print(f"   已覆盖:      {total - missing}")
    print(f"   缺失:        {missing}")
    print(f"   完整度 OK:   {clean}")
    print(f"   记录不足:    {short}")
    print(f"   数据过期:    {stale}")
    print(f"   总记录数:    {total_records:,}")
    print(f"   最少:        {min_code} ({min_rec}条)")
    print(f"   最多:        {max_code} ({max_rec}条)")
    print(f"  【周线】")
    print(f"   已覆盖:      {total - w_miss - w_short}")
    print(f"   周数不足:    {w_short}")
    print(f"   缺失:        {w_miss}")
    print(f"   总记录数:    {weekly_total:,}")
    print(f"{'='*50}")
    
    if verbose and issues:
        print("\n详细问题：")
        for typ, code, desc in issues:
            name = next((e["name"] for e in pool if e["code"] == code), "?")
            print(f"  [{typ}] {code} {name}: {desc}")
    
    return clean, short, missing

def cmd_update():
    """Update short-record ETFs using Sina API."""
    pool = load_pool()
    needs_update = []
    
    for e in pool:
        code = e["code"]
        fp = HISTORY / f"{code}.json"
        raw = read_json_safe(fp)
        records = get_records(raw) if raw else []
        if len(records) < MIN_RECORDS:
            needs_update.append(code)
    
    if not needs_update:
        print("✅ 所有标的记录充足，无需更新。")
        return
    
    print(f"📥 需要更新 {len(needs_update)} 个标的（记录 < {MIN_RECORDS}）：")
    success = 0
    for i, code in enumerate(needs_update):
        name = next((e["name"] for e in pool if e["code"] == code), "?")
        print(f"  [{i+1}/{len(needs_update)}] {code} {name} ...", end="", flush=True)
        
        time.sleep(random.uniform(*API_DELAY))
        records = download_any(code)
        
        if records and len(records) >= MIN_RECORDS:
            out = {"code": code, "name": name, "records": records}
            write_json_safe(HISTORY / f"{code}.json", out)
            print(f" ✓ {len(records)}条 ({records[0]['date']} ~ {records[-1]['date']})")
            success += 1
        else:
            n = len(records) if records else 0
            print(f" ✗ 下载失败或不足 ({n}条)")
    
    if success > 0:
        print(f"\n📊 日线更新完成。正在同步周线...")
        cmd_sync_weekly(quiet=True)
    
    print(f"\n更新结果: {success}/{len(needs_update)}")
    return success

def cmd_sync_weekly(quiet=False):
    """Sync weekly data from daily for all pool ETFs."""
    pool = load_pool()
    total = len(pool)
    updated = 0
    skipped = 0
    errors = 0
    
    if not quiet:
        print(f"从日线同步周线 ({total}只)...")
    
    for i, e in enumerate(pool):
        code = e["code"]
        name = e.get("name", "")
        
        if not quiet and (i+1) % 50 == 0:
            print(f"  [{i+1}/{total}] ...")
        
        try:
            wk_count, changed = sync_weekly_for_code(code, name)
            if changed:
                updated += 1
            else:
                skipped += 1
        except Exception as ex:
            if not quiet:
                print(f"  ✗ {code}: {ex}")
            errors += 1
    
    if not quiet:
        print(f"  完成: {updated}个更新, {skipped}个未变, {errors}个错误")
        print(f"  周线目录: {LONG_V2}")
    
    return updated

def is_qdii(code):
    """判断是否为QDII/跨境标的"""
    pool = load_pool()
    for e in pool:
        if e["code"] == code:
            return e.get("type","") in ("QDII-E(跨境)", "QDII-A(主动)") or code in ("518850",)
    return False


def download_any(code, datalen=100):
    """多源下载：A股用 Sina，QDII/跨境直接用 Tencent ifzq
    
    QDII 跳过 Sina（必超时 404/超时），直走 Tencent 提速。
    """
    if is_qdii(code):
        records = download_via_tencent(code, datalen=datalen)
    else:
        records = download_via_sina(code)
        if not records or len(records) < 10:
            records = download_via_tencent(code, datalen=datalen)
    if records and len(records) >= 10:
        return records
    return None


def cmd_incremental(force=False):
    """增量更新日线：检查每只ETF最后日期，只取更新的记录。
    
    包含交易日过滤：周末/节假日记录会被丢弃。
    Sina 主力 → Tencent ifzq 兜底（跨境标的自动覆盖）。
    
    Args:
        force: True=强制重下载所有历史（覆盖原数据），False=默认增量（只追加新记录）
    """
    pool = load_pool()
    today = date.today()
    
    # 始终检查所有文件（去掉 STALE 逻辑：即使昨天刚更新也要检查今日新数据）
    targets = [e["code"] for e in pool]
    label = "全部 " + str(len(targets)) + " 只 ETF" + (" (强制重下载)" if force else "")
    
    print(f"增量更新日线: {label} (交易日过滤开启)")
    print()
    
    updated = skipped = failed = filtered_total = 0
    
    # 分 QDII / A股，QDII 直走腾讯（快），A股走 Sina
    qdii_targets = [c for c in targets if is_qdii(c)]
    a_targets = [c for c in targets if not is_qdii(c)]
    print(f"  A股: {len(a_targets)}只  跨境/QDII: {len(qdii_targets)}只")
    print()
    
    def _update_one(code):
        nonlocal updated, skipped, failed, filtered_total
        fp = HISTORY / f"{code}.json"
        hist = read_json_safe(fp)
        if hist is None:
            failed += 1
            print(f"  {code}: 文件读取失败")
            return
        recs = get_records(hist) if isinstance(hist, dict) else (hist or [])
        last_date = recs[-1]["date"] if recs else ""
        if not force and last_date >= str(today):
            skipped += 1
            return
        try:
            api_data = download_any(code, datalen=100)
            if not api_data:
                failed += 1
                return
            valid = filter_trading_days(api_data)
            removed = len(api_data) - len(valid)
            filtered_total += removed
            if force:
                to_add = valid
            else:
                to_add = [r for r in valid if r.get("date", "") > last_date]
            if not to_add:
                skipped += 1
            else:
                if force:
                    recs = to_add
                else:
                    existing_dates = set(r["date"] for r in recs if isinstance(r, dict) and "date" in r)
                    to_add = [r for r in to_add if r["date"] not in existing_dates]
                    if to_add:
                        recs = recs + to_add
                if to_add:
                    recs.sort(key=lambda x: x.get("date", "") if isinstance(x, dict) else "")
                    if isinstance(hist, dict):
                        hist["records"] = recs
                        hist["update"] = recs[-1]["date"]
                    else:
                        hist = recs
                    write_json_safe(fp, hist)
                    updated += 1
        except Exception as e:
            print(f"  {code}: ERROR {e}")
            failed += 1
    
    print("QDII/跨境...")
    for i, code in enumerate(qdii_targets):
        _update_one(code)
        if (i+1) % 20 == 0:
            print(f"  [{i+1}/{len(qdii_targets)}] 进行中...")
    print(f"  QDII: 更新{updated}只, {skipped}无变化, {failed}失败")
    
    a_updated = updated
    a_skipped = skipped
    a_failed = failed
    print()
    print("A股...")
    for i, code in enumerate(a_targets):
        _update_one(code)
        if (i+1) % 40 == 0:
            cu = updated - a_updated
            cs = skipped - a_skipped
            cf = failed - a_failed
            print(f"  [{i+1}/{len(a_targets)}] 更新{cu}, 无变化{cs}, 失败{cf}")
    
    print()
    print(f"结果: {updated} 更新, {skipped} 无变化, {failed} 失败, {filtered_total} 条非交易日已过滤")
    
    if updated > 0:
        print()
        print("同步周线...")
        cmd_sync_weekly(quiet=True)


def cmd_refresh():
    print("⚠️ 强制刷新请手动确认。使用 update 命令增量补充即可。")

def cmd_cleanup():
    """List non-pool files in both directories."""
    pool = load_pool()
    pool_codes = {e["code"] for e in pool}
    
    for label, d in [("日线 history/", HISTORY), ("周线 long_v2/", LONG_V2)]:
        all_files = {fp.stem for fp in d.glob("*.json") if fp.stem != "_DATA_GUARDIAN_"}
        orphans = sorted(all_files - pool_codes)
        if not orphans:
            print(f"✅ {label}无多余文件。")
        else:
            print(f"📋 {label}发现 {len(orphans)} 个非标文件：")
            for code in orphans:
                fp = d / f"{code}.json"
                size = fp.stat().st_size / 1024
                try:
                    raw = read_json_safe(fp)
                    recs = get_records(raw) if raw else []
                    print(f"  {code}: {len(recs)}条, {size:.0f}KB")
                except:
                    print(f"  {code}: 读取失败, {size:.0f}KB")

def cmd_update_index(codes=None):
    """用 baostock 更新指数文件（如 000300）

    用法:
        python maintain_etf_data.py update-index 000300
        python maintain_etf_data.py update-index 000300 000905
    """
    import baostock as bs
    from datetime import datetime

    if codes is None:
        codes = sys.argv[2:] if len(sys.argv) > 2 else []
    if not codes:
        print("用法: python maintain_etf_data.py update-index <code> [...]")
        return

    bs.login()
    try:
        updated = skipped = failed = 0
        for code in codes:
            # 构造 baostock 代码格式
            c = str(code).strip()
            if c.startswith(("sh", "sz")):
                bs_code = c[:2].lower() + "." + c[2:]
            else:
                mkt = code_market(c)
                bs_code = f"{mkt}.{c}"

            fp = HISTORY / f"{c}.json"
            # 读取本地已有记录
            if fp.exists():
                hist = read_json_safe(fp)
                recs = get_records(hist) if hist else []
            else:
                recs = []
                # 初始化文件
                fp.write_text(json.dumps({"code": c, "name": c, "records": [], "update": ""}, ensure_ascii=False), encoding="utf-8")

            existing_dates = {r["date"] for r in recs}
            last_local = recs[-1]["date"] if recs else ""

            # 取全历史（baostock最多1000条/次）
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date="1990-01-01",
                end_date="2099-12-31",
                frequency="d",
                adjustflag="3"
            )
            if rs.error_code != "0":
                print(f"  {code}: baostock错误 {rs.error_msg}")
                failed += 1
                continue

            new_rows = []
            while rs.next():
                row = rs.get_row_data()
                d = row[0]
                if d not in existing_dates:
                    try:
                        new_rows.append({
                            "date": d,
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "vol": int(float(row[5])),
                        })
                    except (ValueError, TypeError):
                        pass

            new_rows.sort(key=lambda r: r["date"])
            if new_rows:
                recs.extend(new_rows)
                hist = read_json_safe(fp)
                if isinstance(hist, dict):
                    hist["records"] = recs
                    hist["update"] = new_rows[-1]["date"]
                else:
                    hist = recs
                write_json_safe(fp, hist)
                last_new = new_rows[-1]["date"]
                print(f"  {code}: +{len(new_rows)}条 ({last_local or '空'} → {last_new})")
                updated += 1
            else:
                print(f"  {code}: 无新增 (最新={last_local})")
                skipped += 1

        print(f"\n结果: 更新{updated}只, 跳过{skipped}只, 失败{failed}只")
    finally:
        bs.logout()


def cmd_update_indices():
    """更新指数池数据（baostock国内 + yfinance海外）"""
    import baostock as bs
    from pathlib import Path
    
    INDEX_POOL = Path("D:/QClaw_Trading/data/index_pool.json")
    INDEX_HIST = Path("D:/QClaw_Trading/data/index_history")
    INDEX_HIST.mkdir(exist_ok=True)
    
    if not INDEX_POOL.exists():
        print("指数池文件不存在")
        return
    
    pool = json.loads(INDEX_POOL.read_text(encoding="utf-8"))
    indices = pool["data"]
    
    print(f"更新指数池: {len(indices)}只")
    print()
    
    # 分类处理
    cn_indices = [i for i in indices if i["source"] == "baostock"]
    overseas = [i for i in indices if i["source"] == "yfinance"]
    
    updated = skipped = failed = 0
    
    # 国内指数（baostock）
    if cn_indices:
        print(f"国内指数 ({len(cn_indices)}只):")
        bs.login()
        try:
            for idx in cn_indices:
                code = idx["code"]
                name = idx["name"]
                fp = INDEX_HIST / f"{code}.json"
                
                # 构造baostock代码
                c = str(code).strip()
                if c.startswith(("sh", "sz")):
                    bs_code = c[:2].lower() + "." + c[2:]
                else:
                    # 指数代码判断市场
                    if c.startswith(("000", "880")):
                        bs_code = f"sh.{c}"
                    elif c.startswith(("399", "899")):
                        bs_code = f"sz.{c}"
                    else:
                        bs_code = f"sh.{c}"
                
                # 读取本地
                if fp.exists():
                    hist = read_json_safe(fp)
                    recs = get_records(hist) if hist else []
                else:
                    recs = []
                
                existing = {r["date"] for r in recs}
                last_local = recs[-1]["date"] if recs else ""
                
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume",
                    start_date="1990-01-01",
                    end_date="2099-12-31",
                    frequency="d",
                    adjustflag="3"
                )
                
                if rs.error_code != "0":
                    print(f"  {code} {name}: baostock错误 {rs.error_msg}")
                    failed += 1
                    continue
                
                new_rows = []
                while rs.next():
                    row = rs.get_row_data()
                    d = row[0]
                    if d not in existing:
                        try:
                            new_rows.append({
                                "date": d,
                                "open": float(row[1]),
                                "high": float(row[2]),
                                "low": float(row[3]),
                                "close": float(row[4]),
                                "vol": int(float(row[5]))
                            })
                        except:
                            pass
                
                new_rows.sort(key=lambda r: r["date"])
                if new_rows:
                    recs.extend(new_rows)
                    hist = {"code": code, "name": name, "records": recs, "update": new_rows[-1]["date"]}
                    write_json_safe(fp, hist)
                    print(f"  {code} {name}: +{len(new_rows)}条 ({last_local or '空'} → {new_rows[-1]['date']})")
                    updated += 1
                else:
                    print(f"  {code} {name}: 无新增 (最新={last_local})")
                    skipped += 1
        finally:
            bs.logout()
    
    # 海外指数/商品（yfinance）
    if overseas:
        print(f"\n海外指数/商品 ({len(overseas)}只):")
        try:
            import yfinance as yf
        except ImportError:
            print("  yfinance未安装，跳过海外指数")
            print("  安装: pip install yfinance")
            failed += len(overseas)
        else:
            for idx in overseas:
                code = idx["code"]
                name = idx["name"]
                fp = INDEX_HIST / f"{code.replace('^', 'IDX_').replace('=', '_')}.json"
                
                # 读取本地
                if fp.exists():
                    hist = read_json_safe(fp)
                    recs = get_records(hist) if hist else []
                else:
                    recs = []
                
                existing = {r["date"] for r in recs}
                last_local = recs[-1]["date"] if recs else ""
                
                try:
                    ticker = yf.Ticker(code)
                    df = ticker.history(period="max", auto_adjust=False)
                    
                    if df.empty:
                        print(f"  {code} {name}: 无数据")
                        failed += 1
                        continue
                    
                    new_rows = []
                    for idx_row, row in df.iterrows():
                        d = idx_row.strftime("%Y-%m-%d")
                        if d not in existing:
                            new_rows.append({
                                "date": d,
                                "open": float(row["Open"]),
                                "high": float(row["High"]),
                                "low": float(row["Low"]),
                                "close": float(row["Close"]),
                                "vol": int(row["Volume"]) if row["Volume"] > 0 else 0
                            })
                    
                    new_rows.sort(key=lambda r: r["date"])
                    if new_rows:
                        recs.extend(new_rows)
                        hist = {"code": code, "name": name, "records": recs, "update": new_rows[-1]["date"]}
                        write_json_safe(fp, hist)
                        print(f"  {code} {name}: +{len(new_rows)}条 ({last_local or '空'} → {new_rows[-1]['date']})")
                        updated += 1
                    else:
                        print(f"  {code} {name}: 无新增 (最新={last_local})")
                        skipped += 1
                except Exception as e:
                    print(f"  {code} {name}: 错误 {e}")
                    failed += 1
                
                time.sleep(0.5)  # 避免限流
    
    # 更新池文件
    pool["last_update"] = str(date.today())
    INDEX_POOL.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n结果: 更新{updated}只, 跳过{skipped}只, 失败{failed}只")
    print(f"数据目录: {INDEX_HIST}")


def cmd_update_all():
    """一键更新：ETF池 + 指数池"""
    print("="*50)
    print("一键更新数据（ETF池 + 指数池）")
    print("="*50)
    print()
    
    print("[1/2] ETF池...")
    cmd_incremental(force=False)
    
    print()
    print("[2/2] 指数池...")
    cmd_update_indices()
    
    print()
    print("="*50)
    print("全部更新完成")
    print("="*50)


if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == "check":
        cmd_check(verbose="-v" in sys.argv or "--verbose" in sys.argv)
    elif cmd == "update":
        cmd_update()
        cmd_check(verbose=False)
    elif cmd == "incremental" or cmd == "inc":
        force = "--force" in sys.argv or "-f" in sys.argv
        cmd_incremental(force=force)
    elif cmd == "sync-weekly":
        cmd_sync_weekly()
    elif cmd == "refresh":
        cmd_refresh()
    elif cmd == "cleanup":
        cmd_cleanup()
    elif cmd == "update-index":
        cmd_update_index()
    elif cmd == "update-indices":
        cmd_update_indices()
    elif cmd == "update-all":
        cmd_update_all()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
