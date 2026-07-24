# check history records
import json, os
HIST = r'D:\QClaw_Trading\data\history_long_v2'
for code in ['159837', '560080']:
    path = os.path.join(HIST, code + '.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        recs = d.get('records', [])
        last = recs[-1] if recs else {}
        print(code + ': ' + str(len(recs)) + ' records, last_date=' + str(last.get('date', 'N/A')))
        # show last 3 records
        for r in recs[-3:]:
            print('  ' + str(r.get('date')) + ' close=' + str(r.get('close')))
    else:
        print(code + ': file not found')
