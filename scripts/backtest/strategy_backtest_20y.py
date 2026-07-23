# -*- coding: utf-8 -*-
"""
一号策略：20日均线+MACD策略 - 20年完整回测
包含：五星评分、相关性筛选、资金滚动
"""
import sys
import json
import warnings
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import akshare as ak

# ============================================================
# 配置参数
# ============================================================
INITIAL_CAPITAL = 100000.0  # 初始资金
MAX_POSITIONS = 5           # 最大持仓数
STOP_LOSS = 0.05            # 硬性止损
MAX_CORR = 0.70             # 相关性上限
MA_PERIOD = 20              # MA周期
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ETF池（选择有较长历史的代表ETF）
ETF_POOL = [
    {"code": "510300", "name": "沪深300ETF", "index": "000300", "start": "2012-05-28"},
    {"code": "510500", "name": "中证500ETF", "index": "000905", "start": "2013-03-15"},
    {"code": "159915", "name": "创业板ETF", "index": "399006", "start": "2011-09-20"},
    {"code": "513100", "name": "纳指ETF", "index": "NDX", "start": "2013-04-25"},
    {"code": "518880", "name": "黄金ETF", "index": "XAU", "start": "2013-07-29"},
    {"code": "512100", "name": "中证1000ETF", "index": "000852", "start": "2016-03-28"},
    {"code": "159919", "name": "沪深300ETF(嘉实)", "index": "000300", "start": "2012-05-28"},
    {"code": "510050", "name": "上证50ETF", "index": "000016", "start": "2004-01-01"},
    {"code": "159901", "name": "深证100ETF", "index": "399330", "start": "2006-03-24"},
    {"code": "512010", "name": "医药ETF", "index": "000827", "start": "2013-12-04"},
]

# 基准指数
BENCHMARKS = [
    {"code": "000300", "name": "沪深300"},
    {"code": "000905", "name": "中证500"},
    {"code": "000001", "name": "上证指数"},
    {"code": "399006", "name": "创业板指"},
    {"code": "000852", "name": "中证1000"},
    {"code": "000016", "name": "上证50"},
]


# ============================================================
# 数据获取
# ============================================================
def fetch_etf_data(code: str, start: str = "20050101", end: str = "20260418") -> Optional[pd.DataFrame]:
    """获取ETF日K线数据"""
    try:
        df = ak.fund_etf_hist_sina(symbol=code)
        if df is None or len(df) < 50:
            return None
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={
            "date": "date", "open": "open", "close": "close",
            "high": "high", "low": "low", "volume": "volume"
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 过滤日期范围
        start_dt = pd.to_datetime(start[:4] + "-" + start[4:6] + "-" + start[6:])
        end_dt = pd.to_datetime(end[:4] + "-" + end[4:6] + "-" + end[6:])
        df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
        
        return df[["date", "open", "high", "low", "close", "volume"]].dropna()
    except Exception as e:
        print(f"  获取ETF {code} 失败: {e}")
        return None


def fetch_index_data(code: str, start: str = "20050101", end: str = "20260418") -> Optional[pd.DataFrame]:
    """获取指数日K线数据"""
    try:
        # 处理不同类型的指数代码
        if code.startswith("0") and not code.startswith("00"):
            symbol = "sh" + code
        elif code.startswith("3") or code.startswith("00"):
            symbol = "sz" + code
        else:
            symbol = "sh" + code
            
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or len(df) < 50:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        start_dt = pd.to_datetime(start[:4] + "-" + start[4:6] + "-" + start[6:])
        end_dt = pd.to_datetime(end[:4] + "-" + end[4:6] + "-" + end[6:])
        df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
        
        return df[["date", "close"]].rename(columns={"close": "price"}).reset_index(drop=True)
    except Exception as e:
        print(f"  获取指数 {code} 失败: {e}")
        return None


# ============================================================
# 技术指标计算
# ============================================================
def calc_ema(data: List[float], period: int) -> List[float]:
    """计算EMA"""
    k = 2.0 / (period + 1)
    result = [float(data[0])]
    for v in data[1:]:
        result.append(float(v) * k + result[-1] * (1 - k))
    return result


def calc_sma(data: List[float], period: int) -> List[float]:
    """计算简单移动平均"""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(np.nan)
        else:
            result.append(sum(data[i-period+1:i+1]) / period)
    return result


def calc_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
    """计算MACD"""
    if len(closes) < slow + signal + 5:
        return [], [], []
    
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
    signal_line = calc_ema(macd_line, signal)
    hist = [macd_line[i] - signal_line[i] for i in range(len(macd_line))]
    
    return macd_line, signal_line, hist


def calc_ma20(closes: List[float]) -> List[float]:
    """计算MA20"""
    return calc_sma(closes, 20)


def calc_ma50(closes: List[float]) -> List[float]:
    """计算MA50"""
    return calc_sma(closes, 50)


# ============================================================
# 五星评分系统
# ============================================================
def calc_star_rating(
    price: float,
    ma20: float,
    ma50: float,
    ma20_slope: float,
    macd_line: float,
    signal_line: float,
    hist: float,
    hist_prev: float,
    ret_20d: float,
    ret_5d: float,
    benchmark_ret_20d: float,
    benchmark_ret_5d: float,
    volume: float,
    avg_volume: float,
) -> Tuple[float, float, int]:
    """
    计算五星评分
    返回：(上涨概率, 预期涨幅, 星级)
    """
    # 上涨概率评估
    prob = 50.0  # 基准概率
    
    # 趋势因子
    if ma50 > 0 and ma20 > ma50 and price > ma20:
        prob += 25  # 完美多头排列
    elif ma50 > 0 and ma20 > ma50:
        prob += 20  # 中期向上
    elif ma20_slope > 0 and price > ma20:
        prob += 15  # 短期向上
    elif price > ma20:
        prob += 10  # 站上MA20
    
    # 动量因子
    golden_cross = macd_line > signal_line and hist > 0 and hist_prev <= 0
    above_zero = macd_line > 0
    red_expanding = hist > 0 and hist > hist_prev
    
    if above_zero and golden_cross:
        prob += 25  # 零轴上金叉
    elif above_zero:
        prob += 15  # 零轴上运行
    elif golden_cross:
        prob += 10  # 零轴下金叉
    elif above_zero and red_expanding:
        prob += 20  # 零轴上红柱放大
    
    # 相对强弱
    excess_20d = ret_20d - benchmark_ret_20d
    excess_5d = ret_5d - benchmark_ret_5d
    
    if excess_20d > 5:
        prob += 20  # 强势领涨
    elif excess_20d > 0:
        prob += 15  # 跑赢大盘
    elif excess_5d > 0:
        prob += 10  # 近期强势
    
    # 成交量
    if volume > avg_volume * 1.5:
        prob += 15  # 放量
    elif volume > avg_volume:
        prob += 10  # 量能配合
    
    # 概率上限
    prob = min(prob, 75.0)
    
    # 预期涨幅评估
    expected_return = 0.0
    
    # 突破因子
    if price > ma20:
        # 乖离率
        bias = (price - ma20) / ma20 * 100
        if bias < 5:
            expected_return += bias
        else:
            expected_return += 5
    
    # MACD位置
    if above_zero and golden_cross:
        expected_return += 8
    elif above_zero and red_expanding:
        expected_return += 5
    elif golden_cross:
        expected_return += 3
    
    # 趋势斜率
    if ma20_slope > 2:
        expected_return += 4
    elif ma20_slope > 1:
        expected_return += 2
    
    # 预期涨幅上限
    expected_return = min(expected_return, 15.0)
    
    # 综合评分
    score = prob * expected_return / 100.0
    
    # 星级映射
    if score >= 60:
        stars = 5
    elif score >= 40:
        stars = 4
    elif score >= 25:
        stars = 3
    elif score >= 10:
        stars = 2
    else:
        stars = 1
    
    return prob, expected_return, stars


# ============================================================
# 买入信号判断
# ============================================================
def check_buy_signal(
    price: float,
    ma20: float,
    ma20_slope: float,
    macd_line: float,
    signal_line: float,
    hist: float,
    hist_prev: float,
    stars: int,
) -> bool:
    """检查买入信号"""
    if stars < 4:
        return False
    
    # 基本条件
    if price <= ma20:
        return False
    
    # MACD条件
    above_zero = macd_line > 0
    golden_cross = macd_line > signal_line and hist > 0 and hist_prev <= 0
    red_expanding = hist > 0 and hist > hist_prev
    
    # 买入条件：零轴上金叉 或 零轴上红柱放大
    if above_zero and (golden_cross or red_expanding):
        return True
    
    # 5星可以放宽条件
    if stars == 5 and above_zero and macd_line > signal_line:
        return True
    
    return False


# ============================================================
# 卖出信号判断
# ============================================================
def check_sell_signal(
    price: float,
    ma20: float,
    hist_list: List[float],
    buy_price: float,
    stars: int,
) -> Tuple[bool, str]:
    """检查卖出信号"""
    # 条件①：价格跌破MA20
    if price < ma20:
        return True, "跌破MA20"
    
    # 条件②：MACD柱连续3天<0
    if len(hist_list) >= 3 and all(h < 0 for h in hist_list[-3:]):
        return True, "MACD连续绿柱"
    
    # 条件③：硬性止损
    loss = (price - buy_price) / buy_price
    if loss <= -STOP_LOSS:
        return True, f"止损({loss*100:.1f}%)"
    
    # 条件④：星级降为⭐且触发①或②
    if stars == 1:
        if price < ma20:
            return True, "星级1+跌破MA20"
        if len(hist_list) >= 3 and all(h < 0 for h in hist_list[-3:]):
            return True, "星级1+MACD绿柱"
    
    return False, ""


# ============================================================
# 相关性计算
# ============================================================
def calc_correlation(prices1: List[float], prices2: List[float]) -> float:
    """计算两个价格序列的相关系数"""
    if len(prices1) != len(prices2) or len(prices1) < 20:
        return 0.0
    
    # 计算收益率
    ret1 = np.diff(prices1) / prices1[:-1]
    ret2 = np.diff(prices2) / prices2[:-1]
    
    # 过滤无效值
    valid = np.isfinite(ret1) & np.isfinite(ret2)
    ret1 = ret1[valid]
    ret2 = ret2[valid]
    
    if len(ret1) < 10:
        return 0.0
    
    corr = np.corrcoef(ret1, ret2)[0, 1]
    return corr if np.isfinite(corr) else 0.0


# ============================================================
# 回测引擎
# ============================================================
class BacktestEngine:
    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {code: {shares, buy_price, buy_date}}
        self.equity_curve = []
        self.trade_history = []
        self.daily_values = []
        
    def get_equity(self, prices: Dict[str, float]) -> float:
        """计算总资产"""
        equity = self.cash
        for code, pos in self.positions.items():
            if code in prices:
                equity += pos["shares"] * prices[code]
        return equity
    
    def buy(self, code: str, price: float, date: str, shares: int = None):
        """买入"""
        if shares is None:
            # 等权分配
            target_value = self.initial_capital / MAX_POSITIONS
            shares = int(target_value / price)
        
        cost = shares * price
        if cost > self.cash:
            shares = int(self.cash / price)
            cost = shares * price
        
        if shares <= 0:
            return False
        
        self.cash -= cost
        self.positions[code] = {
            "shares": shares,
            "buy_price": price,
            "buy_date": date,
        }
        
        self.trade_history.append({
            "action": "buy",
            "code": code,
            "price": price,
            "shares": shares,
            "date": date,
            "cash_after": self.cash,
        })
        
        return True
    
    def sell(self, code: str, price: float, date: str, reason: str = ""):
        """卖出"""
        if code not in self.positions:
            return False
        
        pos = self.positions[code]
        proceeds = pos["shares"] * price
        self.cash += proceeds
        
        ret = (price - pos["buy_price"]) / pos["buy_price"]
        
        self.trade_history.append({
            "action": "sell",
            "code": code,
            "price": price,
            "shares": pos["shares"],
            "date": date,
            "cash_after": self.cash,
            "buy_price": pos["buy_price"],
            "return": ret,
            "reason": reason,
        })
        
        del self.positions[code]
        return True
    
    def record_daily(self, date: str, prices: Dict[str, float]):
        """记录每日资产"""
        equity = self.get_equity(prices)
        self.daily_values.append({
            "date": date,
            "equity": equity,
            "cash": self.cash,
            "positions": len(self.positions),
        })
        self.equity_curve.append(equity)


# ============================================================
# 主回测函数
# ============================================================
def run_backtest(start_date: str = "20050101", end_date: str = "20260418"):
    """运行完整回测"""
    print("=" * 70)
    print("  一号策略：20日均线+MACD策略 - 20年完整回测")
    print("=" * 70)
    print(f"  初始资金: {INITIAL_CAPITAL:,.0f}元")
    print(f"  回测区间: {start_date} ~ {end_date}")
    print(f"  最大持仓: {MAX_POSITIONS}只")
    print(f"  相关性上限: {MAX_CORR}")
    print()
    
    # Step 1: 获取数据
    print("[Step 1/5] 获取ETF数据...")
    etf_data = {}
    for etf in ETF_POOL:
        print(f"  {etf['name']}({etf['code']})... ", end="")
        df = fetch_etf_data(etf["code"], start_date, end_date)
        if df is not None and len(df) >= 100:
            etf_data[etf["code"]] = df
            print(f"OK ({len(df)}条, {df['date'].min().strftime('%Y-%m-%d')}~{df['date'].max().strftime('%Y-%m-%d')})")
        else:
            print("FAIL")
    
    if not etf_data:
        print("ERROR: 无有效数据")
        return
    
    # 对齐日期
    all_dates = set()
    for df in etf_data.values():
        all_dates.update(df["date"].tolist())
    all_dates = sorted(all_dates)
    
    print(f"\n  共同交易日: {len(all_dates)}天")
    print(f"  时间跨度: {all_dates[0].strftime('%Y-%m-%d')} ~ {all_dates[-1].strftime('%Y-%m-%d')}")
    
    # Step 2: 获取基准数据
    print("\n[Step 2/5] 获取基准指数...")
    benchmark_data = {}
    for bm in BENCHMARKS:
        print(f"  {bm['name']}({bm['code']})... ", end="")
        df = fetch_index_data(bm["code"], start_date, end_date)
        if df is not None and len(df) >= 100:
            benchmark_data[bm["code"]] = df
            print(f"OK ({len(df)}条)")
        else:
            print("FAIL")
    
    # Step 3: 计算技术指标
    print("\n[Step 3/5] 计算技术指标...")
    etf_indicators = {}
    for code, df in etf_data.items():
        closes = df["close"].tolist()
        volumes = df["volume"].tolist()
        
        # MA
        ma20 = calc_ma20(closes)
        ma50 = calc_ma50(closes)
        
        # MACD
        macd_line, signal_line, hist = calc_macd(closes)
        
        # MA20斜率（5日变化率）
        ma20_slope = [0.0] * len(closes)
        for i in range(5, len(closes)):
            if not np.isnan(ma20[i]) and not np.isnan(ma20[i-5]):
                ma20_slope[i] = (ma20[i] - ma20[i-5]) / ma20[i-5] * 100
        
        etf_indicators[code] = {
            "df": df,
            "closes": closes,
            "volumes": volumes,
            "ma20": ma20,
            "ma50": ma50,
            "ma20_slope": ma20_slope,
            "macd_line": macd_line,
            "signal_line": signal_line,
            "hist": hist,
        }
        print(f"  {code} 指标计算完成")
    
    # Step 4: 运行回测
    print("\n[Step 4/5] 运行策略回测...")
    engine = BacktestEngine(INITIAL_CAPITAL)
    
    # 用于存储每日评分
    daily_ratings = {}
    
    # 遍历每个交易日
    for i, date in enumerate(all_dates):
        date_str = date.strftime("%Y-%m-%d")
        
        # 获取当日价格
        daily_prices = {}
        daily_indicators = {}
        
        for code, ind in etf_indicators.items():
            df = ind["df"]
            # 找到当天的数据
            mask = df["date"] == date
            if mask.any():
                idx = df[mask].index[0]
                daily_prices[code] = ind["closes"][idx]
                daily_indicators[code] = {
                    "idx": idx,
                    "indicators": ind,
                }
        
        if not daily_prices:
            continue
        
        # 计算当日每个ETF的评分
        ratings = []
        for code, price in daily_prices.items():
            ind_data = daily_indicators[code]
            idx = ind_data["idx"]
            ind = ind_data["indicators"]
            
            # 获取指标值
            ma20 = ind["ma20"][idx]
            ma50 = ind["ma50"][idx]
            ma20_slope = ind["ma20_slope"][idx]
            macd_line = ind["macd_line"][idx] if idx < len(ind["macd_line"]) else 0
            signal_line = ind["signal_line"][idx] if idx < len(ind["signal_line"]) else 0
            hist = ind["hist"][idx] if idx < len(ind["hist"]) else 0
            hist_prev = ind["hist"][idx-1] if idx > 0 and idx-1 < len(ind["hist"]) else 0
            
            # 计算收益率
            ret_20d = 0.0
            ret_5d = 0.0
            if idx >= 20:
                ret_20d = (ind["closes"][idx] - ind["closes"][idx-20]) / ind["closes"][idx-20] * 100
            if idx >= 5:
                ret_5d = (ind["closes"][idx] - ind["closes"][idx-5]) / ind["closes"][idx-5] * 100
            
            # 基准收益率（使用沪深300作为基准）
            benchmark_ret_20d = 0.0
            benchmark_ret_5d = 0.0
            if "000300" in benchmark_data:
                bm_df = benchmark_data["000300"]
                bm_mask = bm_df["date"] == date
                if bm_mask.any():
                    bm_idx = bm_df[bm_mask].index[0]
                    if bm_idx >= 20:
                        benchmark_ret_20d = (bm_df["price"].iloc[bm_idx] - bm_df["price"].iloc[bm_idx-20]) / bm_df["price"].iloc[bm_idx-20] * 100
                    if bm_idx >= 5:
                        benchmark_ret_5d = (bm_df["price"].iloc[bm_idx] - bm_df["price"].iloc[bm_idx-5]) / bm_df["price"].iloc[bm_idx-5] * 100
            
            # 成交量
            volume = ind["volumes"][idx]
            avg_volume = np.mean(ind["volumes"][max(0, idx-20):idx+1]) if idx >= 0 else volume
            
            # 计算星级
            if not np.isnan(ma20) and not np.isnan(ma50):
                prob, exp_ret, stars = calc_star_rating(
                    price, ma20, ma50, ma20_slope,
                    macd_line, signal_line, hist, hist_prev,
                    ret_20d, ret_5d, benchmark_ret_20d, benchmark_ret_5d,
                    volume, avg_volume
                )
                
                ratings.append({
                    "code": code,
                    "price": price,
                    "stars": stars,
                    "prob": prob,
                    "exp_ret": exp_ret,
                    "ma20": ma20,
                    "ma20_slope": ma20_slope,
                    "macd_line": macd_line,
                    "signal_line": signal_line,
                    "hist": hist,
                    "hist_prev": hist_prev,
                    "idx": idx,
                    "indicators": ind,
                })
        
        # 存储评分
        daily_ratings[date_str] = ratings
        
        # 检查卖出信号（先检查持仓）
        for code in list(engine.positions.keys()):
            if code in daily_prices:
                pos = engine.positions[code]
                price = daily_prices[code]
                
                # 找到该ETF的评分
                rating = next((r for r in ratings if r["code"] == code), None)
                if rating:
                    # 获取历史MACD柱
                    idx = rating["idx"]
                    ind = rating["indicators"]
                    hist_list = ind["hist"][max(0, idx-10):idx+1]
                    
                    should_sell, reason = check_sell_signal(
                        price, rating["ma20"], hist_list,
                        pos["buy_price"], rating["stars"]
                    )
                    
                    if should_sell:
                        engine.sell(code, price, date_str, reason)
        
        # 检查买入信号
        if len(engine.positions) < MAX_POSITIONS:
            # 筛选4星以上
            buy_candidates = [r for r in ratings if r["stars"] >= 4]
            
            # 按评分排序
            buy_candidates.sort(key=lambda x: x["prob"] * x["exp_ret"], reverse=True)
            
            # 相关性筛选
            selected = []
            for cand in buy_candidates:
                if cand["code"] in engine.positions:
                    continue
                
                # 计算与已选持仓的相关性
                can_add = True
                for held_code in list(engine.positions.keys()) + [s["code"] for s in selected]:
                    if held_code in etf_indicators and cand["code"] in etf_indicators:
                        # 使用过去60天的数据计算相关性
                        idx = cand["idx"]
                        if idx >= 60:
                            prices1 = etf_indicators[held_code]["closes"][idx-60:idx]
                            prices2 = etf_indicators[cand["code"]]["closes"][idx-60:idx]
                            corr = calc_correlation(prices1, prices2)
                            if corr > MAX_CORR:
                                can_add = False
                                break
                
                if can_add:
                    # 检查买入信号
                    if check_buy_signal(
                        cand["price"], cand["ma20"], cand["ma20_slope"],
                        cand["macd_line"], cand["signal_line"],
                        cand["hist"], cand["hist_prev"], cand["stars"]
                    ):
                        selected.append(cand)
                        if len(engine.positions) + len(selected) >= MAX_POSITIONS:
                            break
            
            # 执行买入
            for cand in selected:
                if len(engine.positions) >= MAX_POSITIONS:
                    break
                engine.buy(cand["code"], cand["price"], date_str)
        
        # 记录每日资产
        engine.record_daily(date_str, daily_prices)
        
        # 进度显示
        if (i + 1) % 500 == 0:
            equity = engine.get_equity(daily_prices)
            print(f"  进度: {i+1}/{len(all_dates)} ({(i+1)/len(all_dates)*100:.1f}%)  资产: ¥{equity:,.0f}")
    
    # Step 5: 生成报告
    print("\n[Step 5/5] 生成回测报告...")
    
    # 计算策略绩效
    if engine.daily_values:
        final_equity = engine.daily_values[-1]["equity"]
        total_return = (final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL
        
        # 年化收益
        days = len(engine.daily_values)
        years = days / 252.0
        annual_return = (final_equity / INITIAL_CAPITAL) ** (1.0 / years) - 1
        
        # 夏普比率
        equity_series = np.array([v["equity"] for v in engine.daily_values])
        returns = np.diff(equity_series) / equity_series[:-1]
        returns = returns[np.isfinite(returns)]
        sharpe = (np.mean(returns) / max(np.std(returns), 1e-10)) * np.sqrt(252)
        
        # 最大回撤
        peak = INITIAL_CAPITAL
        max_dd = 0.0
        for v in engine.daily_values:
            peak = max(peak, v["equity"])
            dd = (peak - v["equity"]) / peak
            max_dd = max(max_dd, dd)
        
        # 胜率
        win_trades = [t for t in engine.trade_history if t["action"] == "sell" and t.get("return", 0) > 0]
        sell_trades = [t for t in engine.trade_history if t["action"] == "sell"]
        win_rate = len(win_trades) / len(sell_trades) if sell_trades else 0.0
    else:
        final_equity = INITIAL_CAPITAL
        total_return = 0
        annual_return = 0
        sharpe = 0
        max_dd = 0
        win_rate = 0
        years = 0
    
    # 打印结果
    print("\n" + "=" * 70)
    print("  回测结果")
    print("=" * 70)
    print(f"  回测期间: {all_dates[0].strftime('%Y-%m-%d')} ~ {all_dates[-1].strftime('%Y-%m-%d')} ({years:.1f}年)")
    print(f"  初始资金: {INITIAL_CAPITAL:,.0f}元")
    print(f"  最终资产: {final_equity:,.0f}元")
    print(f"  总收益率: {total_return*100:+.2f}%")
    print(f"  年化收益: {annual_return*100:+.2f}%")
    print(f"  夏普比率: {sharpe:.2f}")
    print(f"  最大回撤: {max_dd*100:.2f}%")
    print(f"  胜率:     {win_rate*100:.1f}%")
    print(f"  交易次数: {len([t for t in engine.trade_history if t['action'] == 'sell'])}次")
    
    # 基准对比
    print("\n" + "=" * 70)
    print("  基准对比（Buy & Hold）")
    print("=" * 70)
    
    benchmark_returns = {}
    for code, df in benchmark_data.items():
        # 对齐日期
        df_aligned = df[df["date"].isin(all_dates)]
        if len(df_aligned) >= 2:
            bm_start = df_aligned["price"].iloc[0]
            bm_end = df_aligned["price"].iloc[-1]
            bm_total = (bm_end - bm_start) / bm_start
            bm_annual = (bm_end / bm_start) ** (252.0 / len(df_aligned)) - 1
            benchmark_returns[code] = {
                "total": bm_total,
                "annual": bm_annual,
            }
            
            # 对比
            diff = annual_return - bm_annual
            print(f"  {next((b['name'] for b in BENCHMARKS if b['code'] == code), code):12s}  "
                  f"年化{bm_annual*100:+6.2f}%  总收益{bm_total*100:+7.2f}%  "
                  f"超额{diff*100:+6.2f}%")
    
    # 保存结果
    result = {
        "strategy": "一号策略",
        "version": "v3.1",
        "backtest_period": f"{all_dates[0].strftime('%Y-%m-%d')} ~ {all_dates[-1].strftime('%Y-%m-%d')}",
        "years": round(years, 2),
        "initial_capital": INITIAL_CAPITAL,
        "final_equity": final_equity,
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "n_trades": len([t for t in engine.trade_history if t["action"] == "sell"]),
        "benchmark": benchmark_returns,
        "trade_history": engine.trade_history[-50:],  # 最近50笔交易
        "daily_values": engine.daily_values[-252:] if len(engine.daily_values) > 252 else engine.daily_values,
    }
    
    out_path = "D:/QClaw_Trading/scripts/backtest/strategy_backtest_20y_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")
    
    # 保存完整交易记录
    trades_path = "D:/QClaw_Trading/scripts/backtest/strategy_backtest_20y_trades.json"
    with open(trades_path, "w", encoding="utf-8") as f:
        json.dump(engine.trade_history, f, ensure_ascii=False, indent=2)
    print(f"交易记录已保存: {trades_path}")
    
    return result


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    result = run_backtest("20050101", "20260418")
