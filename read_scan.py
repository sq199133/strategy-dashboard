import json

with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260704_164149.json', encoding='utf-8') as f:
    data = json.load(f)

print('=== 562500 完整数据 ===')
for etf in data['all']:
    if etf['code'] == '562500':
        for k, v in etf.items():
            if isinstance(v, float):
                if abs(v) < 10:
                    print(f'  {k}: {v:.6f}  ({v*100:.4f}%)')
                else:
                    print(f'  {k}: {v}')
            else:
                print(f'  {k}: {v}')
        break

print()
print('=== TOP3 ===')
for i, t in enumerate(data['target']):
    print(f'#{i+1} {t["code"]} score={t["score"]*100:.2f}% mom={t["mom"]*100:.2f}%')

print()
print('=== 得分排序 TOP10 ===')
all_sorted = sorted(data['all'], key=lambda x: x['score'], reverse=True)
for i, e in enumerate(all_sorted[:10]):
    print(f'{i+1}. {e["code"]} score={e["score"]*100:.2f}% passed={e["passed"]} c_pattern={e.get("c_pattern","?")}')
