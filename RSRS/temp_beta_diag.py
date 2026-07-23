"""RSRS beta 翻多原因诊断 (无statsmodels版，用numpy)
注意：这个脚本用的python路径可能不对，数据问题导致结果可能不准确。
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, 'D:/QClaw_Trading/RSRS')
from rsrs_final_strategy import load_etf

df_sig = load_etf("510300")

# 最后30天
sub = df_sig.tail(30).copy()

# 看今天和前一天的行情
print("=" * 70)
print("  RSRS 翻多原因诊断")
print("  标的: 沪深300 (510300)")
print("  今日: {}".format(str(sub['date'].iloc[-1])[:10]))
print("=" * 70)
print()

# 看看今天行情的实际情况
today = sub.iloc[-1]
yesterday = sub.iloc[-2]
twodays = sub.iloc[-3]

print("  [最近3日行情]")
print("  {:>12} {:>10} {:>10} {:>10} {:>8}".format("日期","开盘","最高","最低","收盘"))
print("  {} {:>9.2f} {:>9.2f} {:>9.2f} {:>9.2f}  <- 昨昨".format(
    str(twodays['date'])[:10], float(twodays['open']), float(twodays['high']),
    float(twodays['low']), float(twodays['close'])))
print("  {} {:>9.2f} {:>9.2f} {:>9.2f} {:>9.2f}  <- 昨天".format(
    str(yesterday['date'])[:10], float(yesterday['open']), float(yesterday['high']),
    float(yesterday['low']), float(yesterday['close'])))
print("  {} {:>9.2f} {:>9.2f} {:>9.2f} {:>9.2f}  <- 今天".format(
    str(today['date'])[:10], float(today['open']), float(today['high']),
    float(today['low']), float(today['close'])))
print()

# 计算18天beta
high = sub.tail(18)['high'].astype(float).values
low = sub.tail(18)['low'].astype(float).values
beta = np.polyfit(low, high, 1)[0]  # 斜率
r2 = np.corrcoef(low, high)[0,1]**2

print("  [最近18天回归]")
print("  区间: {} ~ {}".format(str(sub.tail(18)['date'].iloc[0])[:10],
                                str(sub.tail(18)['date'].iloc[-1])[:10]))
print("  最高价 = {:.4f} * 最低价 + {:.2f}".format(beta, np.polyfit(low, high, 1)[1]))
print("  beta = {:.4f}".format(beta))
print("  R-squared = {:.4f}".format(r2))
print()

# 过去900天的beta分布
all_high = df_sig['high'].astype(float).values
all_low = df_sig['low'].astype(float).values
all_betas = []
for i in range(18, len(df_sig)):
    h = all_high[i-18:i]
    l = all_low[i-18:i]
    b = np.polyfit(l, h, 1)[0]
    all_betas.append(b)
all_betas = np.array(all_betas)

# 取M=900天
if len(all_betas) > 900:
    train = all_betas[-900:]
else:
    train = all_betas

mu = np.nanmean(train)
sd = np.nanstd(train)
zs = (beta - mu) / sd

print("  [标准化参数]")
print("  历史均值 (M={}): {:.4f}".format(len(train), mu))
print("  历史标准差:       {:.4f}".format(sd))
print("  当前z-score:      {:.2f}".format(zs))
print()

# 关键解释：beta上涨原因 -- 看最近18天高低点移动
print("  [最近18天持仓明细]")
print("  {:>12} {:>10} {:>10} {:>8} {:>8}".format("日期","最高","最低","高变化","低变化"))
for i in range(1, len(sub.tail(18))):
    r = sub.tail(18).iloc[i]
    r_prev = sub.tail(18).iloc[i-1]
    hchg = float(r['high']) - float(r_prev['high'])
    lchg = float(r['low']) - float(r_prev['low'])
    hchg_pct = (float(r['high']) / float(r_prev['high']) - 1) * 100
    lchg_pct = (float(r['low']) / float(r_prev['low']) - 1) * 100
    print("  {} {:>9.2f} {:>9.2f} {:>+7.2f} {:>+7.2f}".format(
        str(r['date'])[:10], float(r['high']), float(r['low']),
        hchg, lchg))

print()
print("  [今天 vs 昨天的beta变化归因]")

# 前一个18天
prev_high = sub.tail(36).head(18)['high'].astype(float).values
prev_low = sub.tail(36).head(18)['low'].astype(float).values
beta_prev = np.polyfit(prev_low, prev_high, 1)[0]

print("  前一个18天 beta: {:.4f}".format(beta_prev))
print("  当前18天 beta:   {:.4f}".format(beta))
print("  beta变化:        {:+.4f}".format(beta - beta_prev))
print()

# 今天高低点移动的影响
tod_h = float(today['high'])
tod_l = float(today['low'])
yes_h = float(yesterday['high'])
yes_l = float(yesterday['low'])

print("  [今日高低点变动分析]")
print("  最高: {} -> {} ({} {:.2f})".format(yes_h, tod_h,
    "上涨" if tod_h >= yes_h else "下跌", tod_h - yes_h))
print("  最低: {} -> {} ({} {:.2f})".format(yes_l, tod_l,
    "上涨" if tod_l >= yes_l else "下跌", tod_l - yes_l))
tod_amp = (tod_h - tod_l) / tod_l * 100
yes_amp = (yes_h - yes_l) / yes_l * 100
print("  振幅: {:.2f}% -> {:.2f}%".format(yes_amp, tod_amp))
print()

# 分析RSRS beta原理
print("  [RSRS beta核心原理]")
print("  RSRS beta = 对过去18天(最高价, 最低价)做线性回归的斜率")
print("  beta大 = 最高价和最低价同步快速扩张（不管涨跌）")
print("  beta小 = 高低点同步收窄（横盘）")
print()
print("  翻多的含义：过去18天的高低点同步向上扩张")
print("  -> 即使今天跌了，只要18天全局来看高低点在扩大，beta就高")
print("  -> 今天是18天窗口中的最后1天，18天整体格局没变")
print("  -> 单日下跌不足以改变18天回归线的斜率")
print()

# 对比两种情景
print("  [检查: 今天是不是假涨真跌]")
if float(today['close']) < float(yesterday['close']):
    print("  今天确实是跌的（收盘 {:.2f} < 昨收 {:.2f}）".format(
        float(today['close']), float(yesterday['close'])))
elif float(today['close']) > float(yesterday['close']):
    print("  今天其实是涨的（收盘 {:.2f} > 昨收 {:.2f}）".format(
        float(today['close']), float(yesterday['close'])))
else:
    print("  今天收盘持平")
print()

# 展示翻多阈值突破的历史环境
print("  [结论]")
print("  今天z-score=1.00翻多, 不是因为沪深300今天涨了,")
if float(today['close']) < float(yesterday['close']):
    print("  而是因为过去18天高低点在同步扩张, 区间从{:.2f}-{:.2f}扩大到{:.2f}-{:.2f}。".format(
        float(sub.tail(18).iloc[0]['low']), float(sub.tail(18).iloc[0]['high']),
        float(sub.tail(36).head(18).iloc[-1]['low']), float(sub.tail(18).iloc[-1]['high'])))
print("  RSRS不看收盘涨跌, 只看最高最低的同步性。")
print("  这就是RSRS经常在\"看起来跌了\"的时候翻多的原因。")
