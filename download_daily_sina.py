#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载ETF日线数据（Sina财经API，未复权，2010年起）
保存：D:\QClaw_Trading\data\daily_sina\{code}.json
"""
import sys, json, os, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r'D:\QClaw_Trading\data\daily_sina'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
os.makedirs(DATA_DIR, exist_ok=True)

def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', data.get('etfs', []))

def fetch_sina(code, prefix):
    """Sina财经K线接口（未复权）"""
    # scale=240 是日线（240分钟）
    url = ('http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
             'CN_MarketData.getKLineData?symbol=%s%s&scale=240&ma=no&datalen=1023'
             % (prefix, code))
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        if not raw or raw == 'null':
            return None, 'null'
        d = json.loads(raw)
        records = []
        for rec in d:
            try:
                records.append({
                    'date': rec['day'],
                    'open': float(rec['open']),
                    'close': float(rec['close']),
                    'high': float(rec['high']),
                    'low': float(rec['low']),
                    'volume': float(rec['volume'])
                })
            except (ValueError, KeyError):
                continue
        return records, None
    except Exception as e:
        return None, str(e)

def main():
    pool = load_pool()
    total = len(pool)
    success = 0
    failed = []
    
    print('开始下载 %d 只ETF日线数据（Sina财经，未复权）...' % total)
    print('数据目录：%s' % DATA_DIR)
    print('预计时间：约2分钟\n')
    
    for i, etf in enumerate(pool):
        code = etf['code']
        name = etf.get('name', '')
        out_path = os.path.join(DATA_DIR, '%s.json' % code)
        
        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if len(existing.get('records', [])) > 1000:
                    success += 1
                    if (i + 1) % 20 == 0:
                        print('  [%d/%d] %s %s: SKIP' % (i+1, total, code, name))
                    continue
            except:
                pass
        
        records = None
        for prefix in ['sh', 'sz']:
            records, err = fetch_sina(code, prefix)
            if records and len(records) > 100:
                break
            records = None
        
        if records and len(records) > 100:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump({'code': code, 'name': name, 'records': records},
                         f, ensure_ascii=False)
            success += 1
            print('  [%d/%d] %s %s: %d rows OK' % (i+1, total, code, name, len(records)))
        else:
            failed.append((code, name))
            print('  [%d/%d] %s %s: FAIL' % (i+1, total, code, name))
        
        if (i + 1) % 20 == 0:
            print('  进度: %d/%d (%.1f%%)\n' % (i+1, total, 100*(i+1)/total))
        
        time.sleep(0.1)  # Sina限流较松
    
    print('\n' + '='*60)
    print('下载完成!')
    print('  成功: %d/%d' % (success, total))
    print('  失败: %d' % len(failed))
    if failed:
        print('\n失败列表:')
        for code, name in failed[:20]:
            print('  %s %s' % (code, name))
    print('='*60)
    print('\n⚠️ 注意：Sina数据为未复权，回测需谨慎！')
    print('建议：注册TuShare获取前复权数据')

if __name__ == '__main__':
    main()
