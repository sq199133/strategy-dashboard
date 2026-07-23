"""
Step 1: Download historical daily data for all 13 stocks
Uses baostock (free, no API key needed)
"""
import baostock as bs
import pandas as pd
import os
from datetime import datetime, timedelta

stocks = {
    "300179": "四方达",
    "002222": "福晶科技",
    "688599": "天合光能",
    "300690": "双一科技",
    "301091": "深城交",
    "603322": "超讯科技",
    "300102": "乾照光电",
    "002389": "航天彩虹",
    "300058": "蓝色光标",
    "603901": "永创智能",
    "603667": "五洲新春",
    "603286": "日盈电子",
    "600118": "中国卫星",
}

outdir = r"D:\QClaw_Trading\data"
os.makedirs(outdir, exist_ok=True)

lg = bs.login()
print(f"baostock login: {lg.error_code} {lg.error_msg}")

for code, name in stocks.items():
    # baostock format: sh/sz + code
    prefix = "sh" if code.startswith("6") else "sz"
    bs_code = f"{prefix}.{code}"
    print(f"\nDownloading {bs_code} ({name})...")

    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,high,low,close,volume,amount,peTTM,pbMRQ,isST",
        start_date="2019-01-01",
        end_date="2025-06-17",  # Adjust as needed
        frequency="d",
        adjustflag="2"  # 1=不复权, 2=前复权, 3=后复权
    )

    if rs.error_code != "0":
        print(f"  ERROR: {rs.error_msg}")
        continue

    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    df = pd.DataFrame(rows, columns=rs.fields)

    if df.empty:
        print(f"  No data for {bs_code}")
        continue

    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")
    df = df.dropna(subset=["close", "volume"])
    df = df[df["volume"] > 0]

    fname = os.path.join(outdir, f"{code}_{name}.csv")
    df.to_csv(fname, index=False)
    print(f"  Saved {len(df)} rows → {fname}")

bs.logout()
print("\nDone! All data downloaded.")
