#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 历史数据恢复下载脚本（分批 + 断点续传）
数据源：AKShare stock_zh_a_hist_tx (腾讯财经接口，前复权)
输出目录：D:\QClaw_Trading\data\history_long_v2\（独立目录，不覆盖原文件）
"""
import akshare as ak
import json, os, time, sys
import pandas as pd
from datetime import datetime

OUTPUT_DIR = 'D:/QClaw_Trading/data/history_long_v2'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
PROGRESS_FILE = r'D:\QClaw_Trading\download_progress.json'
BATCH_SIZE = 20  # 每批20只，避免长时间运行被杀死
RATE_LIMIT = 0.7  # 秒/请求
CHUNK_YEARS = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_market(code):
    """ETF前缀判断"""
    c = str(code)
    # 51xxx/52xxx/58xxx → 上海
    if c.startswith('51') or c.startswith('52') or c.startswith('58') or c.startswith('56'):
        # 但 159 开头的不是
        return 'sh'
    # 159xxx/16xxxx → 深圳
    return 'sz'

def download_etf(code):
    """下载单只ETF并转换为周线"""
    market = get_market(code)
    symbol = market + code
    all_rows = []
    
    # 分3年段下载
    for year in range(2010, 2027, CHUNK_YEARS):
        chunk_end = min(year + CHUNK_YEARS - 1, 2026)
        sdate = f'{year}0101'
        edate = f'{chunk_end}1231'
        for retry in range(3):
            try:
                time.sleep(RATE_LIMIT)
                df = ak.stock_zh_a_hist_tx(
                    symbol=symbol,
                    start_date=sdate,
                    end_date=edate,
                    adjust='qfq'
                )
                if df is not None and len(df) > 0:
                    all_rows.append(df)
                break
            except Exception as e:
                if retry < 2:
                    time.sleep(3)
                else:
                    raise
    
    if not all_rows:
        return None
    
    # 合并
    full = pd.concat(all_rows, ignore_index=True)
    full = full.drop_duplicates(subset=['日期'])
    full = full.sort_values('日期')
    full.columns = [c.strip() for c in full.columns]
    
    # 日期列
    date_col = [c for c in full.columns if '日期' in c or 'date' in c.lower()]
    if not date_col:
        return None
    dc = date_col[0]
    full[dc] = pd.to_datetime(full[dc])
    
    # 列名标准化
    rename = {}
    for c in full.columns:
        if '开盘' in c or 'open' in c.lower(): rename[c] = 'open'
        elif '收盘' in c or 'close' in c.lower(): rename[c] = 'close'
        elif '最高' in c or 'high' in c.lower(): rename[c] = 'high'
        elif '最低' in c or 'low' in c.lower(): rename[c] = 'low'
        elif '成交' in c or 'volume' in c.lower() or 'amount' in c.lower(): rename[c] = 'volume'
    full = full.rename(columns=rename)
    
    # 转周线
    full['week'] = full[dc].dt.isocalendar().year.astype(str) + '-W' + full[dc].dt.isocalendar().week.astype(str).str.zfill(2)
    weekly = full.groupby('week').agg({
        'close': 'last',
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'volume': 'sum'
    }).reset_index()
    weekly['date'] = full.groupby('week')[dc].last().values
    
    records = []
    for _, row in weekly.iterrows():
        records.append({
            'w': row['week'],
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
            'close': round(float(row['close']), 4),
            'open': round(float(row['open']), 4),
            'high': round(float(row['high']), 4),
            'low': round(float(row['low']), 4),
            'vol': int(float(row['volume'])) if str(row['volume']) != 'nan' else 0
        })
    
    return records

def main():
    # 读取ETF池
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        raw = f.read().replace('NaN', 'null').replace('Infinity', 'null')
    pool = json.loads(raw)
    
    if 'data' in pool:
        codes = [item['code'] for item in pool['data']]
    else:
        codes = [item['code'] if isinstance(item, dict) else item for item in pool]
    
    codes = [str(c).strip().split('.')[0] for c in codes]
    codes = sorted(set(codes))
    
    # 已下载的跳过
    downloaded = set(f.replace('.json', '') for f in os.listdir(OUTPUT_DIR) if f.endswith('.json'))
    
    # 加载进度（已成功的不重复下载）
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
    
    pending = [c for c in codes if c not in downloaded and c not in progress.get('done', [])]
    
    print(f"ETF池共 {len(codes)} 只")
    print(f"已下载 {len(downloaded)} 只")
    print(f"还需下载 {len(pending)} 只")
    print(f"分批处理，每批 {BATCH_SIZE} 只\n")
    
    done = progress.get('done', []) + list(downloaded)
    failed = progress.get('failed', [])
    
    # 分批处理
    total_pending = len(pending)
    processed = 0
    
    for batch_start in range(0, len(pending), BATCH_SIZE):
        batch = pending[batch_start:batch_start + BATCH_SIZE]
        
        for i, code in enumerate(batch):
            print(f"[{processed+1}/{total_pending}] {code} ... ", end='', flush=True)
            try:
                records = download_etf(code)
                if records and len(records) > 50:
                    path = os.path.join(OUTPUT_DIR, f'{code}.json')
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(records, f, ensure_ascii=False)
                    date_range = f"{records[0]['date']} ~ {records[-1]['date']}"
                    print(f"OK ({len(records)}周, {date_range})")
                    done.append(code)
                else:
                    print(f"数据不足 ({len(records) if records else 0}行)")
                    failed.append(code)
            except Exception as e:
                print(f"FAIL: {e}")
                failed.append(code)
            
            processed += 1
        
        # 每批保存进度
        progress = {'done': list(set(done)), 'failed': list(set(failed))}
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f, ensure_ascii=False)
        
        print(f"\n=== 批次完成: 已成功 {len(set(done))}, 失败 {len(set(failed))} ===\n")
        time.sleep(1)  # 批次间休息
    
    print(f"\n{'='*50}")
    print(f"全部完成!")
    print(f"成功: {len(set(done))} 只")
    print(f"失败: {len(set(failed))} 只")
    if failed:
        print(f"失败列表: {list(set(failed))}")

if __name__ == '__main__':
    main()
