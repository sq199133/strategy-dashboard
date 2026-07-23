# -*- coding: utf-8 -*-
"""
============================================================================
个股多因子选股策略 —— 基于 BaoStock 财务 + 行情数据
============================================================================

策略: 沪深300 / 中证500 成分股内, 用财务因子构建综合得分, 每月选得分最高的
      前 N 只等权持有 (个股多因子等权轮动)。

因子 (F = factor value):
  F1_ROE      = dupontROE          (杜邦ROE,  越高越好)
  F2_Growth   = YOYNI             (净利润同比增长率, 越高越好)
  F3_Leverage = liabilityToAsset  (资产负债率, 越低越好)
  F4_Size     = log(总市值)        (总市值=总股本×复权价, 越低越好)

综合得分 (截面 z-score 后):
  score = z(F1) + z(F2) - z(F3) - z(F4)

回测: 每月末调仓, 选 score 最高的 top_n 只等权持有, 持有至下月末。
基准: 沪深300指数 (sh.000300)。

数据来源 (BaoStock):
  query_hs300_stocks / query_zz500_stocks  成分股
  query_dupont_data   -> dupontROE
  query_growth_data   -> YOYNI
  query_balance_data  -> liabilityToAsset
  query_profit_data   -> totalShare (算市值)  + roeAvg
  query_history_k_data_plus -> 日K线(前复权)

特性:
  - 自动重连 (bs_core.BSHelper)
  - 财务数据 / 行情数据 落盘缓存 (data/fin, data/price), 可断点续跑
  - 抽样模式 (--sample N) 先验证框架, 再全量 (--sample 0)
  - 输出: 权益曲线 CSV, 因子 IC 表, 因子组合对比表

用法:
  python stock_multifactor.py --sample 30          # 抽样30只验证
  python stock_multifactor.py --sample 0           # 全量800只(耗时较长)
  python stock_multifactor.py --sample 30 --skip-download   # 仅用缓存重算
============================================================================
"""
import os, sys, argparse, time, json, csv, math
from datetime import datetime, timedelta

BASE = r"D:\QClaw_Trading"
DATA = os.path.join(BASE, "data", "baostock_stocks")
sys.path.insert(0, DATA)

import baostock as bs
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from bs_core import BSHelper, fetch_all

# ----------------------------- 路径与配置 ---------------------------------
FIN_DIR = os.path.join(DATA, "fin")
PRICE_DIR = os.path.join(DATA, "price")
os.makedirs(FIN_DIR, exist_ok=True)
os.makedirs(PRICE_DIR, exist_ok=True)

CONSTITUENTS_CSV = os.path.join(DATA, "constituents.csv")
REF_DATE = "2026-07-10"
BACKTEST_START = "2016-01-01"
BACKTEST_END = "2026-07-10"

FIN_START_YEAR = 2015   # 为 2016 年初调仓提供可用财报
FIN_END_YEAR = 2025

QUARTERS = [1, 2, 3, 4]
SLEEP_BETWEEN = 0.12     # 限流, 避免被 ban


# ============================ 1. 股票池 ====================================
def load_universe(sample=30, universe="combined"):
    """读取成分股池, 返回 code 列表。sample>0 时取前 N 只抽样验证。"""
    if not os.path.exists(CONSTITUENTS_CSV):
        raise FileNotFoundError("constituents.csv 不存在, 请先运行 build_constituents.py")
    df = pd.read_csv(CONSTITUENTS_CSV, dtype={"code": str})
    if universe == "hs300":
        df = df[df["source"].str.contains("hs300")]
    elif universe == "zz500":
        df = df[df["source"].str.contains("zz500")]
    df = df.sort_values("code").reset_index(drop=True)
    if sample and sample > 0:
        df = df.head(sample)
    return df["code"].tolist(), dict(zip(df["code"], df["name"]))


# ============================ 2. 财务因子 ==================================
def _to_float(x):
    try:
        if x is None or x == "" or x == " ":
            return None
        return float(x)
    except Exception:
        return None


def _fetch_quarter_table(h, fn, code, year, q, field_map):
    """拉取单个财报表某一季度, 返回 {pubDate, statDate, **fields} 或 None。"""
    rs = h.query(fn, code=code, year=str(year), quarter=str(q))
    rows = fetch_all(rs)
    if not rows:
        return None
    row = rows[-1]  # 取最新一条
    f = rs.fields
    rec = {}
    for target, src in field_map.items():
        if src in f:
            rec[target] = row[f.index(src)]
        else:
            rec[target] = None
    rec["pubDate"] = row[f.index("pubDate")] if "pubDate" in f else None
    rec["statDate"] = row[f.index("statDate")] if "statDate" in f else None
    return rec


def fetch_financials(codes, force=False):
    """为每只股票拉取季频财务因子历史, 缓存到 data/fin/{code}.csv。"""
    h = BSHelper.get()
    cols = ["pubDate", "statDate", "dupontROE", "YOYNI",
            "liabilityToAsset", "totalShare", "roeAvg"]
    results = {}
    for ci, code in enumerate(codes):
        path = os.path.join(FIN_DIR, f"{code}.csv")
        if os.path.exists(path) and not force:
            try:
                results[code] = pd.read_csv(path)
                continue
            except Exception:
                pass
        print(f"[fin] ({ci+1}/{len(codes)}) {code}", flush=True)
        records = []
        for year in range(FIN_START_YEAR, FIN_END_YEAR + 1):
            for q in QUARTERS:
                dp = _fetch_quarter_table(h, bs.query_dupont_data, code, year, q,
                                          {"dupontROE": "dupontROE"})
                gr = _fetch_quarter_table(h, bs.query_growth_data, code, year, q,
                                          {"YOYNI": "YOYNI"})
                bl = _fetch_quarter_table(h, bs.query_balance_data, code, year, q,
                                          {"liabilityToAsset": "liabilityToAsset"})
                pf = _fetch_quarter_table(h, bs.query_profit_data, code, year, q,
                                          {"totalShare": "totalShare", "roeAvg": "roeAvg"})
                if not (dp or gr or bl or pf):
                    continue
                pub = (dp or gr or bl or pf).get("pubDate")
                stat = (dp or gr or bl or pf).get("statDate")
                rec = {
                    "pubDate": pub, "statDate": stat,
                    "dupontROE": _to_float((dp or {}).get("dupontROE")),
                    "YOYNI": _to_float((gr or {}).get("YOYNI")),
                    "liabilityToAsset": _to_float((bl or {}).get("liabilityToAsset")),
                    "totalShare": _to_float((pf or {}).get("totalShare")),
                    "roeAvg": _to_float((pf or {}).get("roeAvg")),
                }
                records.append(rec)
                time.sleep(SLEEP_BETWEEN)
        df = pd.DataFrame(records, columns=cols)
        if not df.empty:
            df = df.dropna(subset=["pubDate"]).sort_values("pubDate").reset_index(drop=True)
        df.to_csv(path, index=False)
        results[code] = df
    return results


# ============================ 3. 行情 =====================================
def fetch_prices(codes, force=False):
    """批量拉取前复权日K线, 缓存到 data/price/{code}.csv。"""
    h = BSHelper.get()
    results = {}
    for ci, code in enumerate(codes):
        path = os.path.join(PRICE_DIR, f"{code}.csv")
        if os.path.exists(path) and not force:
            try:
                results[code] = pd.read_csv(path)
                continue
            except Exception:
                pass
        print(f"[price] ({ci+1}/{len(codes)}) {code}", flush=True)
        rs = h.query(bs.query_history_k_data_plus, code,
                     "date,open,high,low,close,volume,amount",
                     start_date=BACKTEST_START, end_date=BACKTEST_END,
                     frequency="d", adjustflag="2")
        rows = fetch_all(rs)
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount"])
        for c in ["open", "high", "low", "close", "volume", "amount"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        df.to_csv(path, index=False)
        results[code] = df
        time.sleep(SLEEP_BETWEEN)
    return results


def fetch_benchmark():
    """沪深300指数日线 (sh.000300) 作为基准。"""
    path = os.path.join(PRICE_DIR, "sh.000300_bench.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    h = BSHelper.get()
    rs = h.query(bs.query_history_k_data_plus, "sh.000300",
                 "date,close", start_date=BACKTEST_START, end_date=BACKTEST_END,
                 frequency="d", adjustflag="3")
    rows = fetch_all(rs)
    df = pd.DataFrame(rows, columns=["date", "close"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    df.to_csv(path, index=False)
    return df


# ===================== 4. 因子构造 (point-in-time) ========================
def build_factor_panel(fin_dict, price_dict, names):
    """
    构造截面因子面板。
    返回 dict: rebal_date -> DataFrame[code, F1_ROE, F2_Growth, F3_Leverage, F4_Size, close]
    其中因子取 rebal_date 当日已发布的最新一期财报 (point-in-time, 避免前视)。
    """
    # 统一交易日历 (所有股票 + 基准的交集交易日)
    all_dates = set()
    for code, df in price_dict.items():
        all_dates.update(df["date"].tolist())
    dates = sorted(all_dates)
    date_set = set(dates)
    # 月末交易日 = 每月最后一个在 date_set 中的日期
    month_last = {}
    for d in dates:
        ym = d[:7]
        month_last[ym] = d
    rebal_dates = sorted(set(month_last.values()))

    # 为每只股票建财报索引: pubDate 列表
    fin_idx = {}
    for code, df in fin_dict.items():
        if df is None or df.empty:
            fin_idx[code] = None
            continue
        fd = df.dropna(subset=["pubDate"]).copy()
        fd["pubDate"] = fd["pubDate"].astype(str)
        fin_idx[code] = fd

    panel = {}
    total = len(rebal_dates)
    for i, rd in enumerate(rebal_dates):
        if (i + 1) % 12 == 0:
            print(f"[factor] building {rd} ({i+1}/{total})", flush=True)
        rows = []
        for code, pdf in price_dict.items():
            # 该交易日收盘价
            sub = pdf[pdf["date"] <= rd]
            if sub.empty:
                continue
            close = float(sub.iloc[-1]["close"])
            # point-in-time 财报: pubDate <= rd 的最近一条
            fd = fin_idx.get(code)
            f1 = f2 = f3 = f4 = None
            if fd is not None and not fd.empty:
                avail = fd[fd["pubDate"] <= rd]
                if not avail.empty:
                    last = avail.iloc[-1]
                    f1 = last.get("dupontROE")
                    f2 = last.get("YOYNI")
                    f3 = last.get("liabilityToAsset")
                    ts = last.get("totalShare")
                    if ts is not None and not math.isnan(ts) and close > 0:
                        f4 = math.log(abs(ts) * close + 1e-9)
            rows.append({
                "code": code, "name": names.get(code, ""),
                "close": close,
                "F1_ROE": f1, "F2_Growth": f2, "F3_Leverage": f3, "F4_Size": f4,
            })
        panel[rd] = pd.DataFrame(rows)
    return panel, rebal_dates


# ===================== 5. 回测引擎 ========================================
def zscore_winsor(s, lower=0.01, upper=0.99):
    """截面 winsorize + z-score。"""
    s = s.astype(float)
    lo, hi = s.quantile(lower), s.quantile(upper)
    s = s.clip(lo, hi)
    mu, sd = s.mean(), s.std()
    if sd == 0 or math.isnan(sd):
        return s * 0.0
    return (s - mu) / sd


def select_top(panel_row, factor_cols, signs, top_n):
    """
    根据因子组合选股。
    factor_cols: 使用的因子列名
    signs: 每个因子的方向 (+1 越大越好, -1 越大越差)
    得分 = sum(sign * zscore(factor))
    """
    df = panel_row.dropna(subset=factor_cols).copy()
    if df.empty:
        return []
    score = pd.Series(0.0, index=df.index)
    for col, sgn in zip(factor_cols, signs):
        z = zscore_winsor(df[col])
        score = score + sgn * z
    df = df.assign(score=score)
    df = df.sort_values("score", ascending=False)
    return df["code"].head(top_n).tolist()


def backtest(panel, rebal_dates, price_dict, factor_cols, signs, top_n,
             cost=0.001):
    """给定因子组合, 跑月度等权回测。返回 equity_df, monthly_ret, holdings。"""
    eq = []
    monthly = []
    holdings_seq = []
    prev_hold = []
    for i, rd in enumerate(rebal_dates):
        row = panel[rd]
        hold = select_top(row, factor_cols, signs, top_n)
        holdings_seq.append((rd, hold))
        # 计算下期收益
        if i + 1 < len(rebal_dates):
            nxt = rebal_dates[i + 1]
            rets = []
            for code in hold:
                pdf = price_dict.get(code)
                if pdf is None or pdf.empty:
                    continue
                p0 = pdf[pdf["date"] <= rd]["close"]
                p1 = pdf[pdf["date"] <= nxt]["close"]
                if p0.empty or p1.empty:
                    continue
                r = float(p1.iloc[-1]) / float(p0.iloc[-1]) - 1.0
                rets.append(r)
            if rets:
                port_ret = np.mean(rets) - cost * 2  # 双边交易成本
            else:
                port_ret = 0.0
        else:
            port_ret = 0.0
        monthly.append({"date": rd, "ret": port_ret, "n_hold": len(hold)})
        eq.append({"date": rd, "equity": None})
    # 累计权益
    eq_val = 1.0
    eq_series = []
    for m in monthly:
        eq_val *= (1 + m["ret"])
        eq_series.append(eq_val)
    out = pd.DataFrame({"date": [m["date"] for m in monthly],
                        "ret": [m["ret"] for m in monthly],
                        "equity": eq_series,
                        "n_hold": [m["n_hold"] for m in monthly]})
    return out, holdings_seq


# ===================== 6. 基准 & 指标 ======================================
def benchmark_series(bench_df, rebal_dates):
    """基准月度收益与权益。"""
    out = []
    eq = 1.0
    for i, rd in enumerate(rebal_dates):
        sub0 = bench_df[bench_df["date"] <= rd]["close"]
        if i + 1 < len(rebal_dates):
            nxt = rebal_dates[i + 1]
            sub1 = bench_df[bench_df["date"] <= nxt]["close"]
            if sub0.empty or sub1.empty:
                r = 0.0
            else:
                r = float(sub1.iloc[-1]) / float(sub0.iloc[-1]) - 1.0
        else:
            r = 0.0
        eq *= (1 + r)
        out.append({"date": rd, "ret": r, "equity": eq})
    return pd.DataFrame(out)


def metrics(series_df, label):
    """series_df: 含 ret, equity。返回指标 dict。"""
    rets = series_df["ret"].dropna().values
    eq = series_df["equity"].values
    n = len(rets)
    if n == 0:
        return {"label": label, "ann_ret": 0, "mdd": 0, "sharpe": 0,
                "win_rate": 0, "final": 1.0}
    years = max(n / 12.0, 1e-9)
    final = eq[-1]
    ann_ret = final ** (1.0 / years) - 1.0 if final > 0 else -1.0
    # MDD
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    mdd = dd.min()
    sharpe = (np.mean(rets) / np.std(rets) * math.sqrt(12)) if np.std(rets) > 0 else 0.0
    win_rate = np.mean(rets > 0)
    return {
        "label": label, "ann_ret": ann_ret, "mdd": mdd, "sharpe": sharpe,
        "win_rate": win_rate, "final": final, "n_months": n,
    }


def ic_analysis(panel, rebal_dates, price_dict, factor_cols, signs):
    """逐因子 IC: 每个调仓日, 因子值与下月收益的 spearman 秩相关。"""
    ic_records = {c: [] for c in factor_cols}
    for i, rd in enumerate(rebal_dates):
        if i + 1 >= len(rebal_dates):
            break
        nxt = rebal_dates[i + 1]
        row = panel[rd]
        # 下月收益
        fwd = {}
        for _, r in row.iterrows():
            code = r["code"]
            pdf = price_dict.get(code)
            if pdf is None or pdf.empty:
                continue
            p0 = pdf[pdf["date"] <= rd]["close"]
            p1 = pdf[pdf["date"] <= nxt]["close"]
            if p0.empty or p1.empty:
                continue
            fwd[code] = float(p1.iloc[-1]) / float(p0.iloc[-1]) - 1.0
        for col in factor_cols:
            sub = row.dropna(subset=[col])
            codes = sub["code"].tolist()
            fvals = sub[col].tolist()
            frets = [fwd.get(c) for c in codes]
            pairs = [(a, b) for a, b in zip(fvals, frets) if b is not None]
            if len(pairs) >= 10:
                a = [p[0] for p in pairs]
                b = [p[1] for p in pairs]
                rho, _ = spearmanr(a, b)
                if not math.isnan(rho):
                    ic_records[col].append(rho)
    summary = {}
    for col, vals in ic_records.items():
        if vals:
            arr = np.array(vals)
            mean_ic = arr.mean()
            std_ic = arr.std()
            icir = mean_ic / std_ic if std_ic > 0 else 0.0
            t = mean_ic / (std_ic / math.sqrt(len(arr))) if std_ic > 0 else 0.0
            hit = np.mean(arr > 0)
            summary[col] = {
                "mean_ic": mean_ic, "std_ic": std_ic, "icir": icir,
                "t_stat": t, "hit_rate": hit, "n": len(arr),
                "dir": "正向" if signs[factor_cols.index(col)] > 0 else "负向",
            }
    return summary


# ===================== 7. 主流程 ==========================================
def run(args):
    print("=== 个股多因子选股策略 ===", flush=True)
    codes, names = load_universe(sample=args.sample, universe=args.universe)
    print(f"股票池: {len(codes)} 只 (sample={args.sample}, universe={args.universe})", flush=True)

    if not args.skip_download:
        print("--- 下载财务因子 ---", flush=True)
        fin_dict = fetch_financials(codes, force=args.force)
        print("--- 下载行情 ---", flush=True)
        price_dict = fetch_prices(codes, force=args.force)
        bench = fetch_benchmark()
    else:
        fin_dict = {c: pd.read_csv(os.path.join(FIN_DIR, f"{c}.csv")) for c in codes}
        price_dict = {c: pd.read_csv(os.path.join(PRICE_DIR, f"{c}.csv")) for c in codes}
        bench = fetch_benchmark()

    print("--- 构造因子面板 ---", flush=True)
    panel, rebal_dates = build_factor_panel(fin_dict, price_dict, names)
    print(f"调仓点数: {len(rebal_dates)} ({rebal_dates[0]} ~ {rebal_dates[-1]})", flush=True)

    bench_eq = benchmark_series(bench, rebal_dates)
    bench_m = metrics(bench_eq, "沪深300基准")

    # 因子组合定义
    ALL = (["F1_ROE", "F2_Growth", "F3_Leverage", "F4_Size"], [+1, +1, -1, -1])
    combos = {
        "ROE_only":      (["F1_ROE"], [+1]),
        "Growth_only":   (["F2_Growth"], [+1]),
        "Leverage_only": (["F3_Leverage"], [-1]),
        "Size_only":     (["F4_Size"], [-1]),
        "ROE+Growth":    (["F1_ROE", "F2_Growth"], [+1, +1]),
        "All4":          ALL,
    }

    results = {}
    for name, (fcols, signs) in combos.items():
        print(f"--- 回测组合: {name} ---", flush=True)
        eq, _ = backtest(panel, rebal_dates, price_dict, fcols, signs, args.top_n)
        m = metrics(eq, name)
        m["excess_ann"] = m["ann_ret"] - bench_m["ann_ret"]
        results[name] = (eq, m)

    # IC 分析 (全因子)
    print("--- 因子 IC 分析 ---", flush=True)
    ic = ic_analysis(panel, rebal_dates, price_dict, ALL[0], {i: s for i, s in enumerate(ALL[1])})

    # 汇总输出
    print("\n================ 回测结果汇总 ================", flush=True)
    hdr = f"{'组合':<14}{'年化':>9}{'MDD':>9}{'Sharpe':>8}{'胜率':>8}{'超额年化':>10}"
    print(hdr)
    for name, (eq, m) in results.items():
        print(f"{name:<14}{m['ann_ret']*100:>8.2f}%{m['mdd']*100:>8.2f}%"
              f"{m['sharpe']:>8.2f}{m['win_rate']*100:>7.1f}%{m['excess_ann']*100:>9.2f}%")
    print(f"{'沪深300基准':<14}{bench_m['ann_ret']*100:>8.2f}%{bench_m['mdd']*100:>8.2f}%"
          f"{bench_m['sharpe']:>8.2f}{bench_m['win_rate']*100:>7.1f}%{'--':>10}")

    print("\n================ 因子 IC ================", flush=True)
    for col, s in ic.items():
        print(f"{col:<14} meanIC={s['mean_ic']:+.4f} ICIR={s['icir']:+.3f} "
              f"t={s['t_stat']:+.2f} hit={s['hit_rate']*100:.1f}% n={s['n']} ({s['dir']})")

    # 保存结果
    out_dir = os.path.join(DATA, "results")
    os.makedirs(out_dir, exist_ok=True)
    # 权益曲线 (All4 + 基准)
    eq_all, _ = results["All4"]
    cmp = pd.DataFrame({"date": eq_all["date"]})
    cmp["strategy"] = eq_all["equity"].values
    cmp["benchmark"] = bench_eq["equity"].values
    cmp.to_csv(os.path.join(out_dir, "equity_curve.csv"), index=False)
    # 指标表
    mt = []
    for name, (eq, m) in results.items():
        mt.append({"combo": name, **m})
    mt.append({"combo": "HS300", **bench_m})
    pd.DataFrame(mt).to_csv(os.path.join(out_dir, "metrics.csv"), index=False)
    # IC 表
    ict = pd.DataFrame([{"factor": k, **v} for k, v in ic.items()])
    ict.to_csv(os.path.join(out_dir, "ic_table.csv"), index=False)

    # 写 json 供文档读取
    summary = {
        "sample": args.sample, "n_stocks": len(codes),
        "top_n": args.top_n, "start": rebal_dates[0], "end": rebal_dates[-1],
        "n_rebal": len(rebal_dates),
        "metrics": {name: {k: (float(v) if isinstance(v, (np.floating, float)) else v)
                           for k, v in m.items()} for name, (eq, m) in results.items()},
        "benchmark": {k: (float(v) if isinstance(v, (np.floating, float)) else v)
                      for k, v in bench_m.items()},
        "ic": {k: {kk: (float(vv) if isinstance(vv, (np.floating, float)) else vv)
                   for kk, vv in v.items()} for k, v in ic.items()},
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {out_dir}", flush=True)
    BSHelper.get().logout()
    return summary


def parse_args():
    p = argparse.ArgumentParser(description="个股多因子选股策略 (BaoStock)")
    p.add_argument("--sample", type=int, default=30,
                   help="抽样股票数 (0=全量800)")
    p.add_argument("--universe", type=str, default="combined",
                   choices=["combined", "hs300", "zz500"])
    p.add_argument("--top-n", type=int, default=20, help="每月持有数量")
    p.add_argument("--force", action="store_true", help="强制重下财务/行情")
    p.add_argument("--skip-download", action="store_true",
                   help="仅用已缓存数据重算")
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(a)
