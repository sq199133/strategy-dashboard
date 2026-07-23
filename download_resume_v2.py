#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 历史数据恢复下载脚本 v2（分批 + 断点续传）
数据源：AKShare stock_zh_a_hist_tx（腾讯财经，前复权）
输出：D:/QClaw_Trading/data/history_long_v2/（独立目录，不覆盖原文件）
"""
import akshare as ak
import json, os, time
import pandas as pd

OUTPUT_DIR = 'D:/QClaw_Trading/data/history_long_v2'
POOL_FILE = 'D:/QClaw_Trading/data/etf_pool_V1_full.json'
PROGRESS_FILE = 'D:/QClaw_Trading/download_progress.json'
BATCH_SIZE = 20
RATE_LIMIT = 0.7
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_market(code):
    c = str(code)
    if c.startswith('51') or c.startswith('52') or c.startswith('58') or c.startswith('56'):
        return 'sh'
    return 'sz'


def download_etf(code):
    """下载单只ETF日线 → 转周线"""
    symbol = get_market(code) + code
    frames = []

    for year in range(2010, 2027, 3):
        ce = min(year + 2, 2026)
        for retry in range(3):
            try:
                time.sleep(RATE_LIMIT)
                df = ak.stock_zh_a_hist_tx(
                    symbol=symbol,
                    start_date=f'{year}0101',
                    end_date=f'{ce}1231',
                    adjust='qfq'
                )
                if df is not None and len(df) > 0:
                    frames.append(df)
                break
            except Exception as e:
                if retry < 2:
                    time.sleep(3)
                else:
                    raise

    if not frames:
        return None

    full = pd.concat(frames, ignore_index=True).drop_duplicates(subset=['date']).sort_values('date')
    full['date'] = pd.to_datetime(full['date'])
    full['amount'] = pd.to_numeric(full['amount'], errors='coerce').fillna(0)

    # 日线转周线
    full['week'] = full['date'].dt.strftime('%G-W%V')
    weekly = full.groupby('week', sort=False).agg({
        'close': 'last', 'open': 'first',
        'high': 'max', 'low': 'min', 'amount': 'sum'
    }).reset_index()
    weekly['date'] = full.groupby('week', sort=False)['date'].last().values

    records = []
    for _, r in weekly.iterrows():
        records.append({
            'w': r['week'],
            'date': r['date'].strftime('%Y-%m-%d'),
            'close': round(float(r['close']), 4),
            'open': round(float(r['open']), 4),
            'high': round(float(r['high']), 4),
            'low': round(float(r['low']), 4),
            'vol': int(r['amount']),
        })
    return records


def main():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        raw = f.read().replace('NaN', 'null').replace('Infinity', 'null')
    pool = json.loads(raw)

    if 'data' in pool:
        all_codes = sorted(set(str(item['code']).split('.')[0] for item in pool['data']))
    else:
        all_codes = sorted(set(str(c).split('.')[0] for c in pool))

    downloaded = set(f.replace('.json', '') for f in os.listdir(OUTPUT_DIR) if f.endswith('.json'))
    progress = json.load(open(PROGRESS_FILE)) if os.path.exists(PROGRESS_FILE) else {}
    done = set(progress.get('done', [])) | downloaded
    failed = set(progress.get('failed', []))
    pending = [c for c in all_codes if c not in done]

    print(f"ETF池共 {len(all_codes)} 只")
    print(f"已下载 {len(done)} 只")
    print(f"还需下载 {len(pending)} 只\n")

    processed = 0
    for batch_start in range(0, len(pending), BATCH_SIZE):
        batch = pending[batch_start:batch_start + BATCH_SIZE]
        for code in batch:
            processed += 1
            print(f"[{processed}/{len(pending)}] {code} ... ", end='', flush=True)
            try:
                records = download_etf(code)
                if records and len(records) > 50:
                    with open(os.path.join(OUTPUT_DIR, f'{code}.json'), 'w', encoding='utf-8') as f:
                        json.dump(records, f, ensure_ascii=False)
                    dr = f"{records[0]['date']} ~ {records[-1]['date']}"
                    print(f"OK ({len(records)}周, {dr})")
                    done.add(code)
                else:
                    print(f"数据不足（{len(records) if records else 0}行）")
                    failed.add(code)
            except Exception as e:
                print(f"FAIL: {e}")
                failed.add(code)

        json.dump({'done': sorted(done), 'failed': sorted(failed)},
                  open(PROGRESS_FILE, 'w'), ensure_ascii=False)
        print(f"=== 批次完成: 成功{len(done)} 失败{len(failed)} ===\n")
        time.sleep(1)

    print(f"\n全部完成！成功{len(done)}只，失败{len(failed)}只")
    if failed:
        print(f"失败列表: {sorted(failed)}")


if __name__ == '__main__':
    main()
