#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载195只ETF前复权日线数据（AKShare，慢速避免限流）
保存目录：D:/QClaw_Trading/data/daily_etf/{code}.json
"""
import sys, json, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r'D:\QClaw_Trading\data\daily_etf'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
os.makedirs(DATA_DIR, exist_ok=True)

DELAY_PER_ETF = 3
MAX_RETRIES = 3

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def download_etf(code, retry=0):
    import akshare as ak
    try:
        df = ak.fund_etf_hist_em(
            symbol=code,
            period='daily',
            start_date='20100101',
            end_date='20260613',
            adjust='hfq'
        )
        if df is None or df.empty:
            return None, 'empty'
        records = []
        for _, row in df.iterrows():
            try:
                records.append({
                    'date': str(row['日期']),
                    'open': float(row['开盘']),
                    'close': float(row['收盘']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'vol': float(row['成交量']),
                })
            except (ValueError, KeyError):
                continue
        return records, None
    except Exception as e:
        if retry < MAX_RETRIES:
            time.sleep(DELAY_PER_ETF * 2)
            return download_etf(code, retry + 1)
        return None, str(e)

def main():
    pool = load_pool()
    total = len(pool)
    success = 0
    failed = []
    skipped = 0

    print('开始下载 {} 只ETF日线数据...'.format(total))
    print('延迟设置: {}秒/只'.format(DELAY_PER_ETF))
    print('数据目录: {}'.format(DATA_DIR))
    print('预计时间: {:.1f} 分钟\n'.format(total * DELAY_PER_ETF / 60))

    start_time = time.time()
    for i, etf in enumerate(pool):
        code = etf['code']
        name = etf.get('name', '')
        out_path = os.path.join(DATA_DIR, '{}.json'.format(code))

        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if len(existing.get('records', [])) > 1000:
                    skipped += 1
                    if (i + 1) % 10 == 0:
                        print('  [{}/{}] {} {}: SKIP'.format(i+1, total, code, name))
                    continue
            except:
                pass

        records, err = download_etf(code)

        if records and len(records) > 100:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump({'code': code, 'name': name, 'records': records}, f, ensure_ascii=False)
            success += 1
            print('  [{}/{}] {} {}: {} rows OK'.format(i+1, total, code, name, len(records)))
        else:
            failed.append((code, name, err))
            print('  [{}/{}] {} {}: FAIL ({})'.format(i+1, total, code, name, err))

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            remaining = (total - i - 1) * avg_time
            print('  进度: {}/{} ({:.1f}%), 剩余: {:.1f} min\n'.format(
                i+1, total, 100*(i+1)/total, remaining/60))

        time.sleep(DELAY_PER_ETF)

    print('\n' + '='*60)
    print('下载完成!')
    print('  成功: {}/{}'.format(success, total))
    print('  跳过: {} (已存在)'.format(skipped))
    print('  失败: {}'.format(len(failed)))
    if failed:
        print('\n失败列表（前20）:')
        for code, name, err in failed[:20]:
            print('  {} {}: {}'.format(code, name, err))
    print('='*60)

if __name__ == '__main__':
    main()
