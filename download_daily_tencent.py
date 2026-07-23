#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载195只ETF日线数据（腾讯API，仅2023-10至今）
输出：D:\QClaw_Trading\data\daily_etf\{code}.json
"""
import sys, json, os, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r'D:\QClaw_Trading\data\daily_etf'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
os.makedirs(DATA_DIR, exist_ok=True)

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def fetch_etf_daily(code, prefix='sz'):
    """从腾讯API获取ETF日线数据（仅2023-10起）"""
    all_records = []
    cur_start = '2023-10-01'
    
    for page in range(20):
        try:
            url = ('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'
                   '_var=kline_day&param={}{},day,{},,640,qfq'.format(
                       prefix, code, cur_start))
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            
            d = json.loads(raw.split('=', 1)[1])
            node = d.get('data', {}).get('{}{}'.format(prefix, code), {})
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
            print('  Page {} error: {}'.format(page+1, e))
            break
    
    return all_records

def main():
    pool = load_pool()
    total = len(pool)
    success = 0
    failed = []
    
    print('开始下载 {} 只ETF日线数据（腾讯API，2023-10起）...'.format(total))
    print('数据目录：{}'.format(DATA_DIR))
    print('预计时间：约5分钟\n')
    
    start_time = time.time()
    
    for i, etf in enumerate(pool):
        code = etf['code']
        name = etf.get('name', '')
        out_path = os.path.join(DATA_DIR, '{}.json'.format(code))
        
        # 跳过已存在
        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if len(existing.get('records', [])) > 300:
                    success += 1
                    if (i + 1) % 20 == 0:
                        print('  [{}/{}] {} {}: SKIP'.format(i+1, total, code, name))
                    continue
            except:
                pass
        
        # 尝试两个前缀
        records = None
        for prefix in ['sz', 'sh']:
            records = fetch_etf_daily(code, prefix)
            if records and len(records) > 50:
                break
            records = None
        
        if records and len(records) > 50:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump({'code': code, 'name': name, 'records': records},
                         f, ensure_ascii=False)
            success += 1
            print('  [{}/{}] {} {}: {} rows OK'.format(
                i+1, total, code, name, len(records)))
        else:
            failed.append((code, name))
            print('  [{}/{}] {} {}: FAIL'.format(i+1, total, code, name))
        
        # 限流
        if (i + 1) % 20 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            remaining = (total - i - 1) * avg_time
            print('  进度: {}/{} ({:.1f}%), 剩余: {:.1f} 分钟\n'.format(
                i+1, total, 100*(i+1)/total, remaining/60))
        
        time.sleep(0.2)  # 快速下载
    
    print('\n' + '='*60)
    print('下载完成!')
    print('  成功: {}/{}'.format(success, total))
    print('  失败: {}'.format(len(failed)))
    if failed:
        print('\n失败列表:')
        for code, name in failed[:20]:
            print('  {} {}'.format(code, name))
    print('='*60)

if __name__ == '__main__':
    main()
