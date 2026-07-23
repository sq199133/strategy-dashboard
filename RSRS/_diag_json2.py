import sys, warnings, json
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

with open(r'D:\QClaw_Trading\RSRS\_diag_out.txt','w',encoding='utf-8') as f:
    for code, name in list(POOL.items())[:3]:  # just first 3 to inspect
        fp = rf'D:\QClaw_Trading\data\history\{code}.json'
        try:
            with open(fp, 'r', encoding='utf-8') as fh:
                content = fh.read()
            j = json.loads(content)
            f.write(f'\n=== {code} {name} ===\n')
            f.write(f'Keys: {list(j.keys())}\n')
            for k, v in j.items():
                if isinstance(v, list):
                    f.write(f'  {k}: len={len(v)}, first={str(v[0])[:100]}, last={str(v[-1])[:100]}\n')
                elif isinstance(v, str):
                    f.write(f'  {k}: {v}\n')
                else:
                    f.write(f'  {k}: {type(v)}\n')
        except Exception as e:
            f.write(f'{code}: ERROR {e}\n')
