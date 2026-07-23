import json

def show(fp, label):
    d = json.load(open(fp))
    s = d['stats']
    print(f'{label}: ann={s["ann_ret"]:+.1f}% dd={s["max_dd"]*100:.1f}% sharpe={s["sharpe"]:.3f} calmar={s.get("calmar",0):.3f}')

show(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260614_234802.json', 'none(基线)')
show(r'D:\Qclaw_Trading\backtest_results\bt_v5_step-5-0.50_20260614_232859.json', 'step:5:0.50')
show(r'D:\Qclaw_Trading\backtest_results\bt_v5_step-3-0.50_20260614_232852.json', 'step:3:0.50')
show(r'D:\Qclaw_Trading\backtest_results\bt_v5_step-4-0.50_20260614_232856.json', 'step:4:0.50')
show(r'D:\Qclaw_Trading\backtest_results\bt_v5_step-5-0.25_20260614_232923.json', 'step:5:0.25')
show(r'D:\Qclaw_Trading\backtest_results\bt_v5_step-2-0.50_20260614_232849.json', 'step:2:0.50')
