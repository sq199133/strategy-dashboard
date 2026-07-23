#!/usr/bin/env python3
# fetch_akshare_full.py - 使用AKShare下载194只ETF完整历史数据
# 用法: python -X utf8 fetch_akshare_full.py [start_idx] [end_idx]

import akshare as ak
import json
import os
import sys
import time
from datetime import datetime

# 配置
POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
HIST_DIR = r"D:\QClaw_Trading\data\history"
SLEEP_SEC = 0.8  # 每次请求间隔（秒），避免被封

# 设置标准输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def load_etf_pool():
    """加载ETF池"""
    try:
        with open(POOL_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # 替换NaN为null
            content = content.replace('NaN', 'null')
            data = json.loads(content)
            return data.get('data', [])
    except Exception as e:
        print(f"读取ETF池失败: {e}")
        sys.exit(1)

def get_exchange(code):
    """判断交易所（根据ETF代码前2位）"""
    prefix = int(code[:2])
    # 上海：50xxxx, 51xxxx, 56xxxx, 58xxxx, 60xxxx
    if 50 <= prefix <= 60:
        return 'SH'
    # 深圳：15xxxx, 16xxxx, 17xxxx, 18xxxx
    return 'SZ'

def fetch_etf_history(code, exchange):
    """使用AKShare下载ETF历史数据"""
    try:
        # 使用东方财富数据源（最稳定）
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date="20000101",
            end_date="20261231",
            adjust=""  # 不复权（如需前复权用"qfq"，后复权用"hfq"）
        )
        
        if df is None or df.empty:
            return None
        
        # 转换格式（与之前腾讯API格式保持一致）
        records = []
        for _, row in df.iterrows():
            record = {
                'date': str(row['日期']),
                'open': float(row['开盘']),
                'close': float(row['收盘']),
                'high': float(row['最高']),
                'low': float(row['最低']),
                'vol': int(row['成交量']) if row['成交量'] > 0 else 0,
                'amount': float(row['成交额']) if row['成交额'] > 0 else 0.0
            }
            records.append(record)
        
        # 按日期升序排列
        records.sort(key=lambda x: x['date'])
        
        return records
        
    except Exception as e:
        print(f"    ❌ 错误: {e}")
        return None

def save_to_json(records, filepath):
    """保存为JSON文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({'records': records}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"    ❌ 保存失败: {e}")
        return False

def main():
    print("=== AKShare ETF历史数据下载 (方案C) ===\n")
    
    # 加载ETF池
    pool = load_etf_pool()
    if not pool:
        print("ETF池为空，退出")
        sys.exit(1)
    
    # 解析命令行参数
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else len(pool)
    
    batch = pool[start_idx:end_idx]
    
    print(f"ETF总数: {len(pool)}")
    print(f"本次批次: {start_idx+1}-{end_idx}")
    print(f"批次大小: {len(batch)}")
    print(f"目标: 获取从上市开始的完整历史\n")
    
    ok = 0
    fail = 0
    failed_list = []
    
    for i, etf in enumerate(batch):
        idx = start_idx + i + 1
        code = etf['code']
        name = etf['name']
        exchange = get_exchange(code)
        symbol = exchange + code
        
        print(f"[{idx}/{len(pool)}] {symbol} {name}... ", end='')
        
        # 下载数据
        records = fetch_etf_history(code, exchange)
        
        if records and len(records) > 0:
            # 保存到文件
            filename = f"{exchange.lower()}{code}.json"
            filepath = os.path.join(HIST_DIR, filename)
            
            if save_to_json(records, filepath):
                print(f"✅ {len(records)}条 ({records[0]['date']} ~ {records[-1]['date']})")
                ok += 1
            else:
                print(f"❌ 保存失败")
                fail += 1
                failed_list.append({'code': code, 'name': name, 'symbol': symbol})
        else:
            print(f"❌ 下载失败（无数据）")
            fail += 1
            failed_list.append({'code': code, 'name': name, 'symbol': symbol})
        
        # 延迟，避免被封
        if i < len(batch) - 1:
            time.sleep(SLEEP_SEC)
    
    # 输出统计
    print(f"\n=== 下载完成 ===")
    print(f"✅ 成功: {ok}")
    print(f"❌ 失败: {fail}")
    
    if failed_list:
        print(f"\n失败列表:")
        for item in failed_list:
            print(f"  {item['symbol']} {item['name']} ({item['code']})")
    
    print(f"\n提示: 失败的ETF可以重新运行脚本，指定start_idx和end_idx重试")

if __name__ == "__main__":
    main()
