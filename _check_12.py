import json
from pathlib import Path

codes = ['513050','159605','513060','513660','513690','513880','513120','513850','513400','162415','520790','159170']
H = Path('D:/QClaw_Trading/data/history')
L = Path('D:/QClaw_Trading/data/history_long_v2')

print('代码      记录数  最早日期    最新日期')
print('-' * 50)
for c in codes:
    hf = H / f'{c}.json'
    if hf.exists():
        d = json.loads(hf.read_text(encoding='utf-8'))
        recs = d.get('records',[])
        name = d.get('name','?')
        if recs:
            print(f'{c} {name[:8]:8s} {len(recs):5d}  {recs[0]["date"]}  {recs[-1]["date"]}')
        else:
            print(f'{c} {name[:8]:8s}   records空')
    else:
        print(f'{c}  文件不存在')
