import json
with open(r'D:\Qclaw_Trading\scan_results\weekly_scan_v4_20260712_111132.json', encoding='utf-8') as f:
    d = json.load(f)
passed = [e for e in d['all'] if e.get('passed')]
passed.sort(key=lambda x: x.get('_adj_score', 0), reverse=True)
print('Qualified ranked:')
for i, e in enumerate(passed):
    print('{}. {} score={:.4f} dev={:+.1f}% mom={:+.1f}% vol={:.2f}'.format(
        i+1, e['code'], e['_adj_score'], e['dev']*100, e['mom']*100, e['vol_ratio']))
print('Total qualified: {}'.format(len(passed)))
