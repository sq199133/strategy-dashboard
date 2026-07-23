#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载195只ETF日线数据（腾讯API，兼容qfqday/day双字段）"""
import sys, json, os, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r'D:\QClaw_Trading\data\daily_tx'
os.makedirs(DATA_DIR, exist_ok=True)
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

def get_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def download_daily_tx(code, prefix='sz', max_retries=2):
    """下载单只ETF日线数据，兼容qfqday/day双字段"""
    all_records = []
    cur_start = '2007-01-01'
    
    for attempt in range(max_retries):
        try:
            url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'
                  f'_var=kline_day&param={prefix}{code},day,{cur_start},,640,qfq')
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            
            raw = raw.strip()
            if not raw.startswith('var'):
                return None
            
            d = json.loads(raw.split('=', 1)[1])
            node = d.get('data', {}).get(f'{prefix}{code}', {})
            qfq_days = node.get('qfqday', [])
            raw_days = node.get('day', [])
            
            # 优先qfqday，其次day
            days = qfq_days if qfq_days else raw_days
            if not days:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
            
            for rec in days:
                if len(rec) >= 6:
                    all_records.append({
                        'date': rec[0],
                        'open': float(rec[1]),
                        'close': float(rec[2]),
                        'high': float(rec[3]),
                        'low': float(rec[4]),
                        'vol': float(rec[5])
                    })
            
            if len(days) < 640:
                break
            cur_start = days[-1][0]
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None
    
    return all_records if len(all_records) > 100 else None

def main():
    pool = get_pool()
    total = len(pool)
    success = 0
    failed = []
    
    for i, etf in enumerate(pool):
        code = etf['code']
        # 自动探测前缀
        for prefix in ['sz', 'sh']:
            out_path = os.path.join(DATA_DIR, f'{code}.json')
            
            # 跳过已下载且数据量足够的
            if os.path.exists(out_path):
                try:
                    with open(out_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                    if len(existing.get('records', [])) > 1000:
                        success += 1
                        break
                except:
                    pass
            
            records = download_daily_tx(code, prefix)
            if records and len(records) > 100:
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump({'code': code, 'records': records}, f, ensure_ascii=False)
                success += 1
                days_count = len(records)
                date_range = f"{records[0]['date']} ~ {records[-1]['date']}"
                print(f'  [{i+1}/{total}] {code}: {days_count} days, {date_range}')
                break
        else:
            failed.append(code)
            print(f'  [{i+1}/{total}] {code}: FAILED')
        
        if (i + 1) % 20 == 0:
            time.sleep(0.5)
    
    print(f'\n结果: 成功 {success}/{total}')
    if failed:
        print(f'失败 ({len(failed)}只): {failed}')

if __name__ == '__main__':
    main()