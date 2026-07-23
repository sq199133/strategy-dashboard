#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare慢速下载195只ETF日线数据（前复权）
接口：akshare.stock_zh_a_hist_tx (adjust='qfq')
限流：2秒/只
支持断点续传
"""
import sys, json, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r'D:\QClaw_Trading\data\daily_tx'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
os.makedirs(DATA_DIR, exist_ok=True)

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def download_daily(code, retry=0):
    """下载单只ETF日线数据（前复权）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist_tx(
            symbol=code,
            start_date='20100101',
            end_date='20260613',
            adjust='qfq'
        )
        if df is None or df.empty:
            return None, 'empty'
        
        records = []
        for _, row in df.iterrows():
            try:
                records.append({
                    'date': str(row['日期']),
                    'open': float(row['开盘']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'close': float(row['收盘']),
                    'vol': float(row['成交量'])
                })
            except (ValueError, KeyError):
                continue
        
        return records, None
    except Exception as e:
        if retry < 3:
            time.sleep(3)
            return download_daily(code, retry + 1)
        return None, str(e)[:200]

def main():
    pool = load_pool()
    total = len(pool)
    success = 0
    failed = []
    
    print(f'开始下载 {total} 只ETF日线数据（AKShare慢速，前复权）...')
    print(f'数据目录：{DATA_DIR}')
    print(f'限流：2秒/只，预计时间：约 {total * 2 / 60:.1f} 分钟\n')
    
    start_time = time.time()
    log_file = os.path.join(DATA_DIR, '_download_log.txt')
    
    for i, etf in enumerate(pool):
        code = etf['code']
        name = etf.get('name', '')
        out_path = os.path.join(DATA_DIR, f'{code}.json')
        
        # 断点续传：跳过已存在且数据量足够
        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if len(existing.get('records', [])) > 1000:
                    success += 1
                    print(f'  [{i+1}/{total}] {code} {name}: SKIP (已存在 {len(existing["records"])} 行)')
                    time.sleep(0.1)
                    continue
            except:
                pass
        
        records, err = download_daily(code)
        
        if records and len(records) > 100:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump({'code': code, 'name': name, 'records': records}, f, ensure_ascii=False)
            success += 1
            print(f'  [{i+1}/{total}] {code} {name}: {len(records)} 行 ✅')
        else:
            failed.append((code, name, err))
            print(f'  [{i+1}/{total}] {code} {name}: ❌ FAIL ({err})')
        
        # 进度报告
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            remaining = (total - i - 1) * avg_time
            print(f'  进度: {i+1}/{total} ({100*(i+1)/total:.1f}%), 剩余: {remaining/60:.1f} 分钟')
            # 写入日志
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {i+1}/{total} 成功:{success} 失败:{len(failed)}\n')
        
        # 限流：2秒/只
        time.sleep(2.0)
    
    # 最终报告
    print(f'\n{"="*60}')
    print(f'下载完成!')
    print(f'  成功: {success}/{total}')
    print(f'  失败: {len(failed)}')
    if failed:
        print(f'\n失败列表:')
        for code, name, err in failed:
            print(f'  {code} {name}: {err}')
    print(f'{"="*60}')
    
    # 保存失败列表
    if failed:
        fail_file = os.path.join(DATA_DIR, '_failed.txt')
        with open(fail_file, 'w', encoding='utf-8') as f:
            for code, name, err in failed:
                f.write(f'{code}\t{name}\t{err}\n')
        print(f'\n失败列表已保存至：{fail_file}')

if __name__ == '__main__':
    main()
