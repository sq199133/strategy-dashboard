#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载完整历史数据脚本 (AKShare + 日线转周线)
使用 akshare.stock_zh_a_hist_tx 获取2010年至今的日线前复权数据
转换为周线（每周最后一个交易日收盘价 + 成交量求和）
输出到 D:\QClaw_Trading\data\history_long\
"""
import akshare as ak
import json, os, time, glob
import pandas as pd
from datetime import datetime

HIST_DIR  = r'D:\QClaw_Trading\data\history_long_v2'
POOL_FILE = r'D:\QClaw_Trading\etf_pool_cn.json'
CHUNK_YEARS = 3  # 每段3年，避免单次请求数据量过大
RATE_LIMIT = 0.7  # 秒/请求（留余量）
SKIP_EXISTING = True  # 已有足够数据的ETF跳过（检查是否覆盖到2010）


def get_market(code):
    """根据ETF代码判断市场前缀"""
    if code.startswith('5') or code.startswith('15'):
        return 'sh'
    elif code.startswith('1') or code.startswith('2') or code.startswith('9'):
        return 'sz'
    elif code.startswith('51') or code.startswith('56') or code.startswith('58'):
        return 'sz'
    elif code.startswith('159') or code.startswith('16'):
        return 'sz'
    return 'sh'


def download_etf_daily(code, start_year=2010, end_year=2026):
    """下载单只ETF日线数据（2010-2026，按3年分段）"""
    market = get_market(code)
    symbol = market + code
    all_rows = []
    
    # 分段下载
    for year in range(start_year, end_year + 1, CHUNK_YEARS):
        chunk_end = min(year + CHUNK_YEARS - 1, end_year)
        sdate = f'{year:04d}0101'
        edate = f'{chunk_end:04d}1231'
        
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
                if retry == 2:
                    pass  # 静默失败，跳过这段
                time.sleep(1.0)
    
    if not all_rows:
        return None
    
    # 合并
    combined = pd.concat(all_rows, ignore_index=True)
    combined = combined.drop_duplicates(subset=['date']).sort_values('date')
    
    # 重命名amount为vol
    if 'amount' in combined.columns:
        combined['vol'] = combined['amount']
    
    return combined


def daily_to_weekly(df):
    """将日线DataFrame转换为周线（每周最后一个收盘价 + 成交量求和）"""
    if df is None or len(df) == 0:
        return []
    
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # 按年-周分组
    df['year'] = df['date'].dt.year
    df['week'] = df['date'].dt.isocalendar().week
    
    # 每周最后一条记录（最后交易日）
    weekly_records = []
    grouped = df.groupby(['year', 'week'])
    
    for (yr, wn), grp in grouped:
        grp = grp.sort_values('date')
        last_row = grp.iloc[-1]
        # 周总成交量
        total_vol = grp['vol'].sum()
        week_key = '%d-W%02d' % (yr, int(wn))
        weekly_records.append({
            'w': week_key,
            'date': last_row['date'].strftime('%Y-%m-%d'),
            'close': float(last_row['close']),
            'open': float(last_row.get('open', last_row['close'])),
            'high': float(last_row.get('high', last_row['close'])),
            'low': float(last_row.get('low', last_row['close'])),
            'vol': float(total_vol),
        })
    
    return weekly_records


def has_good_history(code):
    """检查现有文件是否有足够的历史数据（回溯到2010年）"""
    for pat in [code, f'sh{code}', f'sz{code}', f'*{code}*.json']:
        matches = glob.glob(os.path.join(HIST_DIR, pat.replace('*', '').replace('?', '')))
        if not matches:
            matches = glob.glob(os.path.join(HIST_DIR, f'*{code}*.json'))
        if matches:
            try:
                with open(matches[0], 'r', encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                records = json.loads(raw)
                if isinstance(records, list) and len(records) >= 300:
                    dates = [r['date'] if isinstance(r, dict) else str(r[0]) 
                             for r in records if isinstance(r, dict) and 'date' in r
                             or (isinstance(r, (list, tuple)) and len(r) > 0)]
                    if dates:
                        earliest = min(dates)
                        if earliest <= '2012-01-01':
                            return True
            except:
                pass
    return False


def save_weekly(code, weekly_records):
    """保存周线数据到文件"""
    path = os.path.join(HIST_DIR, f'{code}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(weekly_records, f, ensure_ascii=False, indent=2)


def main():
    # 读取ETF池
    try:
        with open(POOL_FILE, 'r', encoding='utf-8') as f:
            raw = f.read()
        # 尝试解码
        try:
            pool = json.loads(raw)
        except json.JSONDecodeError:
            # GBK编码
            pool = json.loads(raw.encode('gbk').decode('utf-8'))
        if isinstance(pool, list):
            etf_list = pool
        elif isinstance(pool, dict):
            etf_list = pool.get('data', pool.get('etfs', []))
        else:
            etf_list = []
    except Exception as e:
        print(f'Cannot load pool: {e}')
        # 从history_long目录获取代码列表
        existing = [f.replace('.json','') for f in os.listdir(HIST_DIR) 
                    if f.endswith('.json') and f[:6].isdigit()]
        etf_list = [{'code': c} for c in existing]
    
    # 去重并获取代码列表
    codes = []
    seen = set()
    for etf in etf_list:
        code = etf.get('code', '')
        if code and code not in seen and len(code) == 6 and code.isdigit():
            codes.append(code)
            seen.add(code)
    
    print(f'Total ETFs to process: {len(codes)}')
    
    # 也补充一些常见ETF（如果不在列表里）
    common_etfs = [
        '510880', '510300', '510500', '159915', '513500', '510050',
        '159919', '159901', '159902', '159920', '159928', '159941',
        '512000', '512100', '512200', '512010', '512980', '513010',
        '513030', '513050', '513080', '513100', '513500', '513580',
        '515000', '515050', '515080', '515100', '515180', '515880',
    ]
    for c in common_etfs:
        if c not in seen:
            codes.append(c)
            seen.add(c)
    
    print(f'Total with common: {len(codes)}')
    
    os.makedirs(HIST_DIR, exist_ok=True)
    
    success = 0
    failed = []
    skipped = 0
    
    for i, code in enumerate(codes):
        if SKIP_EXISTING and has_good_history(code):
            skipped += 1
            continue
        
        market = get_market(code)
        symbol = market + code
        
        print(f'[{i+1}/{len(codes)}] Downloading {symbol}...', end=' ', flush=True)
        
        try:
            df = download_etf_daily(code, 2010, 2026)
            if df is None or len(df) == 0:
                print('NO DATA')
                failed.append(code)
                continue
            
            weekly = daily_to_weekly(df)
            if len(weekly) < 100:
                print(f'ONLY {len(weekly)} WEEKS - SKIP')
                failed.append(code)
                continue
            
            save_weekly(code, weekly)
            first_date = weekly[0]['date']
            last_date = weekly[-1]['date']
            print(f'{len(weekly)} weeks ({first_date} to {last_date})')
            success += 1
            
        except Exception as e:
            print(f'ERROR: {e}')
            failed.append(code)
    
    print()
    print('='*50)
    print(f'  Done: {success} saved, {skipped} skipped, {len(failed)} failed')
    if failed:
        print(f'  Failed: {failed[:20]}')


if __name__ == '__main__':
    main()
