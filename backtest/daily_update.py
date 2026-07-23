"""
每日数据更新 + 策略信号分配
数据来源: Baostock (沪深A股日线, 支持前复权, 更新至当日)
"""
import baostock as bs
import pandas as pd
import numpy as np
import os, sys
from datetime import datetime, date, timedelta

STOCKS = {
    "300179": "四方达", "002222": "福晶科技", "688599": "天合光能",
    "300690": "双一科技", "301091": "深城交", "603322": "超讯科技",
    "300102": "乾照光电", "002389": "航天彩虹", "300058": "蓝色光标",
    "603901": "永创智能", "603667": "五洲新春", "603286": "日盈电子",
    "600118": "中国卫星",
}

DATA_DIR = r"D:\QClaw_Trading\data"
BACKTEST_DIR = r"D:\QClaw_Trading\backtest"


def bs_code(code):
    """转baostock代码格式"""
    if code.startswith("6"):
        return f"sh.{code}"
    else:
        return f"sz.{code}"


def fetch_baostock(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """用Baostock拉取日线数据（前复权）"""
    try:
        rs = bs.query_history_k_data_plus(
            bs_code(code),
            "date,open,high,low,close,volume,amount",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="2",
        )
        data = []
        while rs.next():
            data.append(rs.get_row_data())
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=["date","open","high","low","close","volume","amount"])
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open","high","low","close","volume","amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.sort_values("date").reset_index(drop=True)

    except Exception as e:
        print(f"    Baostock拉取{code}失败: {e}")
        return pd.DataFrame()


def update_stock_data(code: str, name: str) -> bool:
    """增量更新单只股票数据"""
    csv_path = os.path.join(DATA_DIR, f"{code}_{name}.csv")

    # 确定起始日期
    if os.path.exists(csv_path):
        existing = pd.read_csv(csv_path, encoding="utf-8-sig")
        existing["date"] = pd.to_datetime(existing["date"])
        last_date = existing["date"].max()
        start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = date.today().isoformat()
        if start_date > today_str:
            print(f"  {code} {name}: 已是最新 (截止{last_date.date()})")
            return False
    else:
        start_date = "2019-01-01"
        existing = pd.DataFrame()

    end_date = date.today().isoformat()
    print(f"  {code} {name}: {start_date} ~ {end_date} ...", end=" ")

    new_data = fetch_baostock(code, start_date, end_date)
    if new_data.empty:
        print("无新数据")
        return False

    print(f"{len(new_data)}条", end=" ")

    # 去重
    if not existing.empty:
        existing_dates = set(existing["date"].dt.date)
        new_data = new_data[~new_data["date"].dt.date.isin(existing_dates)]
        if new_data.empty:
            print("(已存在)")
            return False
        combined = pd.concat([existing, new_data], ignore_index=True)
    else:
        combined = new_data

    combined = combined.sort_values("date").reset_index(drop=True)
    combined["code"] = code
    combined.to_csv(csv_path, index=False, encoding="utf-8-sig")

    date_range = f"{combined['date'].min().date()} ~ {combined['date'].max().date()}"
    print(f"✅ 总计{len(combined)}条 ({date_range})")
    return True


def run_allocator():
    """运行策略分配器"""
    import importlib
    # 重新加载以保证最新
    if "strategy_allocator" in sys.modules:
        del sys.modules["strategy_allocator"]
    from strategy_allocator import run_daily_scan, print_report
    result = run_daily_scan()
    print_report(result)
    return result


# ================================================================

if __name__ == "__main__":
    if sys.stdout.encoding != "utf-8":
        sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

    print("=" * 60)
    print(f"  每日量化更新 & 策略信号  |  {date.today().isoformat()}")
    print(f"  来源: Baostock (前复权)  |  标的: {len(STOCKS)}只A股")
    print("=" * 60)
    print()

    # ── Baostock登录 ──
    lg = bs.login()
    if lg.error_code != "0":
        print(f"Baostock登录失败: {lg.error_msg}")
        sys.exit(1)
    print("✅ Baostock 登录成功")

    # ── 1. 更新数据 ──
    print("\n▶ 阶段1: 数据增量更新")
    updated = 0
    for code, name in STOCKS.items():
        try:
            if update_stock_data(code, name):
                updated += 1
        except Exception as e:
            print(f"  ✗ {code} {name}: {e}")

    print(f"\n  更新完成: {updated}/{len(STOCKS)} 只")
    bs.logout()

    # ── 2. 跑分配器 ──
    print("\n▶ 阶段2: 智能策略分配器")
    result = run_allocator()

    # ── 3. 保存 ──
    today = date.today().isoformat()
    report_lines = [
        "=" * 60,
        f"每日量化信号 | {today}",
        f"数据更新: {updated}/{len(STOCKS)} 只",
        "来源: Baostock (前复权)",
        "=" * 60,
        "",
        result["summary"],
    ]
    report = "\n".join(report_lines)

    out_txt = os.path.join(BACKTEST_DIR, f"daily_report_{today}.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n完整报告: {out_txt}")
