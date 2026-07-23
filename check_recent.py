import json
for code in ['159902', '160723', '161128']:
    for prefix in ['sz', 'sh']:
        path = f'D:/QClaw_Trading/data/history/{prefix}{code}.json'
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            recs = data.get('records', [])
            print(f'{code}: 共{len(recs)}条, 最新{recs[-1]["date"]} close={recs[-1]["close"]:.3f}')
            print(f'  最后5条:')
            for r in recs[-5:]:
                print(f'    {r["date"]}: {r["close"]:.3f}')
        except:
            pass