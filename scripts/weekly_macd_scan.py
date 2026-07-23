#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周线MACD扫描器
- 买入信号：本周周线MACD值（DIF）刚大于0（本周DIF>0，上周DIF<=0）
- 卖出信号：本周周线MACD值（DIF）刚小于0（本周DIF<0，上周DIF>=0）
- 数据源：akshare（真实历史数据）
- 标的池：etf_pool_V1_full.json
"""

import json, sys, os, time, datetime
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# ============ 配置 ============
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
SIGNALS_DIR = r'D:\QClaw_Trading\signals'
PORTFOLIO_FILE = r'D:\QClaw_Trading\data\portfolio_macd_weekly.json'

# MACD参数（标准12/26/9）
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

os.makedirs(SIGNALS_DIR, exist_ok=True)


def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    return pool['data']


def fetch_weekly_kline(code, name='', weeks=60):
    """通过akshare获取ETF周K线数据"""
    import akshare as ak
    
    for attempt in range(3):
        try:
            df = ak.fund_etf_hist_em(symbol=str(code), period="weekly", adjust="qfq")
            if df is None or len(df) == 0:
                return None
            
            # akshare返回的列名在Windows可能乱码，用位置索引
            # 0:日期 1:开盘 2:收盘 3:最高 4:最低 5:成交量 6:成交额 7:振幅 8:涨跌幅 9:涨跌额 10:换手率
            df = df.rename(columns={
                df.columns[0]: 'date',
                df.columns[1]: 'open',
                df.columns[2]: 'close',
                df.columns[3]: 'high',
                df.columns[4]: 'low',
                df.columns[5]: 'volume',
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df = df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)
            
            # 只保留最近N周
            if len(df) > weeks:
                df = df.iloc[-weeks:].reset_index(drop=True)
            
            return df
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                return None
    return None


def calc_macd(close_series, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    """计算MACD指标"""
    ema_fast = close_series.ewm(span=fast, adjust=False).mean()
    ema_slow = close_series.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = 2 * (dif - dea)  # MACD柱
    return dif, dea, macd_hist


def scan_signals(etfs):
    """扫描所有ETF的周线MACD信号"""
    buy_signals = []
    sell_signals = []
    failed = []
    
    total = len(etfs)
    for i, etf in enumerate(etfs):
        code = str(etf['code'])
        name = etf.get('name', '')
        
        # 进度
        if (i + 1) % 20 == 0 or i == 0:
            print(f"[{i+1}/{total}] 扫描中...")
        
        # 获取周K线
        df = fetch_weekly_kline(code, name)
        if df is None or len(df) < MACD_SLOW + MACD_SIGNAL + 5:
            failed.append({'code': code, 'name': name, 'reason': f'数据不足或获取失败(需>{MACD_SLOW + MACD_SIGNAL + 5}周)'})
            time.sleep(0.2)
            continue
        
        # 计算MACD
        dif, dea, macd_hist = calc_macd(df['close'])
        df['DIF'] = dif
        df['DEA'] = dea
        df['MACD'] = macd_hist
        
        # 最新两周数据
        if len(df) < 2:
            failed.append({'code': code, 'name': name, 'reason': '数据不足2周'})
            time.sleep(0.2)
            continue
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        dif_this = last['DIF']
        dif_prev = prev['DIF']
        
        # 买入信号：DIF本周>0，上周<=0（MACD线刚上穿零轴）
        if dif_this > 0 and dif_prev <= 0:
            buy_signals.append({
                'code': code,
                'name': name,
                'category': etf.get('category', ''),
                'close': round(last['close'], 4),
                'date': str(last['date'].date()),
                'dif': round(dif_this, 4),
                'dif_prev': round(dif_prev, 4),
                'dea': round(last['DEA'], 4),
                'macd_hist': round(last['MACD'], 4),
            })
        
        # 卖出信号：DIF本周<0，上周>=0（MACD线刚下穿零轴）
        elif dif_this < 0 and dif_prev >= 0:
            sell_signals.append({
                'code': code,
                'name': name,
                'category': etf.get('category', ''),
                'close': round(last['close'], 4),
                'date': str(last['date'].date()),
                'dif': round(dif_this, 4),
                'dif_prev': round(dif_prev, 4),
                'dea': round(last['DEA'], 4),
                'macd_hist': round(last['MACD'], 4),
            })
        
        time.sleep(0.2)  # 避免请求过快
    
    return buy_signals, sell_signals, failed


def generate_report(buy_signals, sell_signals, failed, portfolio):
    """生成信号报告"""
    now = datetime.datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    
    report_lines = []
    report_lines.append(f"# 周线MACD信号报告 - {date_str}")
    report_lines.append(f"")
    report_lines.append(f"扫描时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"标的池：etf_pool_V1_full.json")
    report_lines.append(f"MACD参数：{MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL}")
    report_lines.append(f"信号定义：买入=DIF上穿零轴 | 卖出=DIF下穿零轴")
    report_lines.append(f"说明：同花顺的MACD数值=MACD柱(2×(DIF-DEA))，DIF线=快线-慢线")
    report_lines.append(f"")
    
    # === 买入信号 ===
    report_lines.append(f"## 买入信号")
    report_lines.append(f"")
    if buy_signals:
        # 按类别分组
        categories = {}
        for s in buy_signals:
            cat = s['category'] or '未分类'
            categories.setdefault(cat, []).append(s)
        
        report_lines.append(f"共 {len(buy_signals)} 只ETF出现买入信号：")
        report_lines.append(f"")
        
        for cat in sorted(categories.keys()):
            items = categories[cat]
            report_lines.append(f"**{cat}**（{len(items)}只）：")
            for s in items:
                report_lines.append(f"- {s['name']}（{s['code']}）收盘 {s['close']} | DIF: {s['dif_prev']} → {s['dif']} | MACD柱: {s['macd_hist']}")
            report_lines.append(f"")
        
        # 买入建议
        report_lines.append(f"## 买入建议")
        report_lines.append(f"")
        
        current_holds = len(portfolio.get('positions', []))
        available_slots = 5 - current_holds
        
        if available_slots <= 0:
            report_lines.append(f"当前已满仓（{current_holds}/5），如需换仓请先确认卖出。")
        elif len(buy_signals) <= available_slots:
            report_lines.append(f"买入信号数（{len(buy_signals)}）<= 可用仓位（{available_slots}），可全部考虑买入。")
        else:
            report_lines.append(f"当前持仓 {current_holds}/5，可用仓位 {available_slots}，买入信号 {len(buy_signals)} 只。")
            report_lines.append(f"")
            report_lines.append(f"建议优先考虑：")
            report_lines.append(f"1. 不同类别分散（避免同板块重复）")
            report_lines.append(f"2. 规模大的ETF（流动性好）")
            
            # 按类别去重推荐
            seen_cats = set()
            recommendations = []
            for s in buy_signals:
                cat = s['category'] or '未分类'
                if cat not in seen_cats:
                    seen_cats.add(cat)
                    recommendations.append(s)
                    if len(recommendations) >= available_slots:
                        break
            
            if recommendations:
                report_lines.append(f"")
                report_lines.append(f"按类别分散推荐（最多{available_slots}只）：")
                for i, s in enumerate(recommendations, 1):
                    report_lines.append(f"{i}. {s['name']}（{s['code']}）[{s['category']}]")
        
        report_lines.append(f"")
        report_lines.append(f"> 请确认最终买入标的，我将更新持仓。")
    else:
        report_lines.append(f"本周无买入信号。")
    
    report_lines.append(f"")
    
    # === 卖出信号 ===
    report_lines.append(f"## 卖出信号")
    report_lines.append(f"")
    if sell_signals:
        report_lines.append(f"共 {len(sell_signals)} 只ETF出现卖出信号：")
        report_lines.append(f"")
        for s in sell_signals:
            in_portfolio = any(
                p.get('code') == s['code'] 
                for p in portfolio.get('positions', [])
            )
            hold_tag = " **[持仓中]**" if in_portfolio else ""
            report_lines.append(f"- {s['name']}（{s['code']}）收盘 {s['close']} | DIF: {s['dif_prev']} → {s['dif']} | MACD柱: {s['macd_hist']}{hold_tag}")
    else:
        report_lines.append(f"本周无卖出信号。")
    
    report_lines.append(f"")
    
    # === 当前持仓 ===
    report_lines.append(f"## 当前持仓")
    report_lines.append(f"")
    positions = portfolio.get('positions', [])
    if positions:
        report_lines.append(f"初始资金：{portfolio.get('initial_capital', 50000)}元 | 等权持仓 | 最多5只")
        report_lines.append(f"")
        for p in positions:
            report_lines.append(f"- {p['name']}（{p['code']}）买入价 {p.get('buy_price', 'N/A')} | 买入日期 {p.get('buy_date', 'N/A')}")
    else:
        report_lines.append(f"当前空仓。初始资金：{portfolio.get('initial_capital', 50000)}元")
    
    report_lines.append(f"")
    
    # === 失败列表 ===
    if failed:
        report_lines.append(f"## 数据获取失败（{len(failed)}只）")
        report_lines.append(f"")
        for f_item in failed[:10]:
            report_lines.append(f"- {f_item['name']}（{f_item['code']}）：{f_item['reason']}")
        if len(failed) > 10:
            report_lines.append(f"- ... 共{len(failed)}只失败")
    
    return '\n'.join(report_lines)


def load_portfolio():
    """加载持仓"""
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'initial_capital': 50000,
        'max_positions': 5,
        'equal_weight': True,
        'positions': [],
        'history': []
    }


def main():
    print("=" * 60)
    print("周线MACD信号扫描器")
    print("=" * 60)
    
    # 加载标的池
    etfs = load_pool()
    print(f"标的池加载完成：{len(etfs)} 只ETF")
    
    # 加载持仓
    portfolio = load_portfolio()
    print(f"当前持仓：{len(portfolio.get('positions', []))}/5")
    
    # 扫描信号
    print("\n开始扫描周线MACD信号...")
    buy_signals, sell_signals, failed = scan_signals(etfs)
    
    print(f"\n扫描完成：")
    print(f"  买入信号：{len(buy_signals)} 只")
    print(f"  卖出信号：{len(sell_signals)} 只")
    print(f"  获取失败：{len(failed)} 只")
    
    # 保存信号数据
    now = datetime.datetime.now()
    date_str = now.strftime('%Y%m%d')
    signal_file = os.path.join(SIGNALS_DIR, f'macd_weekly_{date_str}.json')
    signal_data = {
        'scan_date': now.strftime('%Y-%m-%d %H:%M:%S'),
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'failed': failed,
        'params': {'fast': MACD_FAST, 'slow': MACD_SLOW, 'signal': MACD_SIGNAL}
    }
    with open(signal_file, 'w', encoding='utf-8') as f:
        json.dump(signal_data, f, ensure_ascii=False, indent=2)
    print(f"\n信号数据已保存：{signal_file}")
    
    # 生成报告
    report = generate_report(buy_signals, sell_signals, failed, portfolio)
    report_file = os.path.join(SIGNALS_DIR, f'macd_weekly_{date_str}.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"报告已保存：{report_file}")
    
    # 输出报告到stdout
    print("\n" + "=" * 60)
    print(report)


if __name__ == '__main__':
    main()
