#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预下载195只ETF日线数据到本地JSON（腾讯API，兼容qfqday/day）"""
import sys, json, os, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r'D:\QClaw_Trading\data\daily_tx'
os.makedirs(DATA_DIR, exist_ok=True)
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

def get_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def download_etf_daily(code, prefix, max_pages=20):
    """分页下载ETF日线数据"""
    all_records = []
    cur_start = '2007-01-01'
    
    for page in range(max_pages):
        try:
            url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'
                  f'_var=kline_day&param={prefix}{code},day,{cur_start},,640,qfq')
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            
            d = json.loads(raw.split('=', 1)[1])
            node = d.get('data', {}).get(f'{prefix}{code}', {})
            qfq = node.get('qfqday', [])
            raw = node.get('day', [])
            days = qfq if qfq else raw
            
            if not days:
                break
            
            for rec in days:
                if len(rec) >= 6:
                    try:
                        all_records.append({
                            'date': rec[0],
                            'open': float(rec[1]),
                            'close': float(rec[2]),
                            'high': float(rec[3]),
                            'low': float(rec[4]),
                            'vol': float(rec[5])
                        })
                    except (ValueError, TypeError):
                        continue
            
            if len(days) < 640:
                break
            cur_start = days[-1][0]
            
        except Exception as e:
            print(f'    Page {page+1} error: {e}')
            break
    
    return all_records

def main():
    pool = get_pool()
    total = len(pool)
    success = 0
    failed = []
    
    for i, etf in enumerate(pool):
        code = etf['code']
        out_path = os.path.join(DATA_DIR, f'{code}.json')
        
        # Skip already downloaded
        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if len(existing.get('records', [])) > 500:
                    success += 1
                    continue
            except:
                pass
        
        # Try both prefixes
        found = False
        for prefix in ['sz', 'sh']:
            records = download_etf_daily(code, prefix)
            if records and len(records) > 50:
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump({'code': code, 'records': records}, f, ensure_ascii=False)
                success += 1
                print(f'  [{i+1}/{total}] {prefix}{code}: {len(records)} days')
                found = True
                break
        
        if not found:
            failed.append(code)
            print(f'  [{i+1}/{total}] {code}: FAILED')
        
        # Rate limit
        time.sleep(0.15)
        if (i + 1) % 30 == 0:
            time.sleep(1)
    
    print(f'\nDone: {success}/{total}')
    if failed:
        print(f'Failed ({len(failed)}): {failed[:20]}...')

if __name__ == '__main__':
    main()