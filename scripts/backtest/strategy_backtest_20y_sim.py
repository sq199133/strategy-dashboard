# -*- coding: utf-8 -*-
"""Strategy 1 Backtest - Simplified Version"""
import json
import numpy as np
import pandas as pd

np.random.seed(42)

INITIAL = 100000
MAX_POS = 5
STOP = 0.05

def gbm(n, mu, sig, s0=1.0):
    dt = 1/252
    z = np.random.randn(n)
    p = np.zeros(n)
    p[0] = s0
    for i in range(1, n):
        p[i] = p[i-1] * np.exp((mu - 0.5*sig**2)*dt + sig*np.sqrt(dt)*z[i])
    return p

def sma(p, per):
    r = np.full(len(p), np.nan)
    for i in range(per-1, len(p)):
        r[i] = np.mean(p[i-per+1:i+1])
    return r

def ema(p, per):
    r = np.zeros(len(p))
    r[0] = p[0]
    k = 2.0/(per+1)
    for i in range(1, len(p)):
        r[i] = p[i]*k + r[i-1]*(1-k)
    return r

def macd(p):
    e12, e26 = ema(p, 12), ema(p, 26)
    m = e12 - e26
    s = ema(m, 9)
    h = m - s
    return m, s, h

# Generate 20 years of data
print("Strategy 1: MA20+MACD 20-Year Backtest")
print("="*60)

years = 20
n = years * 252
dates = pd.date_range("2006-01-01", periods=n, freq='B')

# ETF data
etfs = {
    "510300": {"name": "HS300", "p": gbm(n, 0.08, 0.20)},
    "510500": {"name": "ZZ500", "p": gbm(n, 0.10, 0.25)},
    "159915": {"name": "CYB", "p": gbm(n, 0.12, 0.30)},
    "513100": {"name": "Nasdaq", "p": gbm(n, 0.13, 0.22)},
    "518880": {"name": "Gold", "p": gbm(n, 0.05, 0.15)},
}

# Benchmarks
bms = {
    "000300": {"name": "HS300Idx", "p": gbm(n, 0.08, 0.20)},
    "000905": {"name": "ZZ500Idx", "p": gbm(n, 0.10, 0.25)},
    "399006": {"name": "CYBIdx", "p": gbm(n, 0.12, 0.30)},
}

print(f"Simulated {n} trading days ({years} years)")

# Calculate indicators
for code in etfs:
    p = etfs[code]["p"]
    etfs[code]["ma20"] = sma(p, 20)
    etfs[code]["ma50"] = sma(p, 50)
    m, s, h = macd(p)
    etfs[code]["macd"] = m
    etfs[code]["sig"] = s
    etfs[code]["hist"] = h

# Backtest
cash = float(INITIAL)
pos = {}  # {code: {shares, price, date}}
trades = []
equity = []

warmup = 50

for i in range(warmup, n):
    date = dates[i].strftime("%Y-%m-%d")
    
    # Current prices
    prices = {code: etfs[code]["p"][i] for code in etfs}
    
    # Calculate equity
    eq = cash
    for c in pos:
        eq += pos[c]["shares"] * prices[c]
    equity.append(eq)
    
    # Check sell
    for c in list(pos.keys()):
        price = prices[c]
        ma20 = etfs[c]["ma20"][i]
        h = etfs[c]["hist"][i-2:i+1] if i >= 2 else [etfs[c]["hist"][i]]
        
        # Sell conditions
        sell = False
        reason = ""
        
        # 1. Below MA20
        if not np.isnan(ma20) and price < ma20:
            sell = True
            reason = "BelowMA20"
        
        # 2. MACD green 3 days
        if len(h) >= 3 and all(x < 0 for x in h):
            sell = True
            reason = "Green3d"
        
        # 3. Stop loss
        loss = (price - pos[c]["price"]) / pos[c]["price"]
        if loss <= -STOP:
            sell = True
            reason = f"StopLoss{loss*100:.1f}%"
        
        if sell:
            cash += pos[c]["shares"] * price
            ret = (price - pos[c]["price"]) / pos[c]["price"]
            trades.append({"act": "sell", "code": c, "price": price, "shares": pos[c]["shares"], 
                          "date": date, "ret": ret, "reason": reason})
            del pos[c]
    
    # Check buy
    if len(pos) < MAX_POS:
        candidates = []
        
        for code in etfs:
            if code in pos:
                continue
            
            price = prices[code]
            ma20 = etfs[code]["ma20"][i]
            m = etfs[code]["macd"][i]
            s = etfs[code]["sig"][i]
            h = etfs[code]["hist"][i]
            hp = etfs[code]["hist"][i-1] if i > 0 else 0
            
            if np.isnan(ma20):
                continue
            
            # Buy condition: price > MA20 and MACD above signal
            if price > ma20 and m > s:
                # Simple rating
                score = 0
                if price > ma20:
                    score += 30
                if m > 0:
                    score += 30
                if h > 0:
                    score += 20
                if m > s:
                    score += 20
                
                stars = min(5, max(1, score // 20))
                candidates.append({"code": code, "stars": stars, "price": price, "score": score})
        
        # Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Buy top candidates
        for c in candidates[:MAX_POS - len(pos)]:
            target = cash / (MAX_POS - len(pos))
            shares = int(target / c["price"])
            if shares > 0 and shares * c["price"] <= cash:
                cost = shares * c["price"]
                cash -= cost
                pos[c["code"]] = {"shares": shares, "price": c["price"], "date": date}
                trades.append({"act": "buy", "code": c["code"], "price": c["price"], 
                              "shares": shares, "date": date, "stars": c["stars"]})
    
    # Progress
    if (i - warmup) % 500 == 0:
        print(f"  Day {i-warmup}/{n-warmup}: Equity {eq:,.0f}, Positions: {len(pos)}")

# Final results
final_eq = equity[-1]
total_ret = (final_eq - INITIAL) / INITIAL
ann_ret = (final_eq / INITIAL) ** (252/len(equity)) - 1

# Sharpe
eq_arr = np.array(equity)
rets = np.diff(eq_arr) / eq_arr[:-1]
rets = rets[np.isfinite(rets)]
sharpe = (np.mean(rets) / max(np.std(rets), 1e-10)) * np.sqrt(252)

# Max drawdown
peak = INITIAL
max_dd = 0
for e in equity:
    peak = max(peak, e)
    dd = (peak - e) / peak
    max_dd = max(max_dd, dd)

# Win rate
sells = [t for t in trades if t["act"] == "sell"]
wins = [t for t in sells if t.get("ret", 0) > 0]
win_rate = len(wins) / len(sells) if sells else 0

print("\n" + "="*60)
print("Results")
print("="*60)
print(f"Period: {dates[warmup].strftime('%Y-%m-%d')} ~ {dates[-1].strftime('%Y-%m-%d')}")
print(f"Years: {len(equity)/252:.1f}")
print(f"Initial: {INITIAL:,}")
print(f"Final: {final_eq:,.0f}")
print(f"Total Return: {total_ret*100:+.2f}%")
print(f"Annual Return: {ann_ret*100:+.2f}%")
print(f"Sharpe: {sharpe:.2f}")
print(f"Max Drawdown: {max_dd*100:.2f}%")
print(f"Win Rate: {win_rate*100:.1f}%")
print(f"Trades: {len(sells)}")

# Benchmark comparison
print("\n" + "="*60)
print("Benchmark Comparison")
print("="*60)

for code, data in bms.items():
    p = data["p"]
    bm_ret = (p[-1] - p[warmup]) / p[warmup]
    bm_ann = (p[-1] / p[warmup]) ** (252/(len(p)-warmup)) - 1
    diff = ann_ret - bm_ann
    print(f"{data['name']:12s}: Annual {bm_ann*100:+6.2f}%  Total {bm_ret*100:+7.2f}%  Excess {diff*100:+6.2f}%")

# Save
result = {
    "strategy": "Strategy 1",
    "period": f"{dates[warmup].strftime('%Y-%m-%d')} ~ {dates[-1].strftime('%Y-%m-%d')}",
    "years": len(equity)/252,
    "initial": INITIAL,
    "final": float(final_eq),
    "total_return": float(total_ret),
    "annual_return": float(ann_ret),
    "sharpe": float(sharpe),
    "max_drawdown": float(max_dd),
    "win_rate": float(win_rate),
    "n_trades": len(sells),
}

with open("D:/QClaw_Trading/scripts/backtest/backtest_20y_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

with open("D:/QClaw_Trading/scripts/backtest/backtest_20y_trades.json", "w", encoding="utf-8") as f:
    json.dump(trades, f, indent=2)

print("\nResults saved.")
