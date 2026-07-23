// ============================================================
// 纯MA20穿越策略回测
// 买入：价格刚站上MA20（前一天在下方，当天在上方）
// 卖出：价格刚跌破MA20（前一天在上方，当天在下方）
// ============================================================
'use strict';

const fs = require('fs');
const path = require('path');

function SMA(prices, n) {
  const out = new Array(prices.length).fill(null);
  for (let i = n - 1; i < prices.length; i++) {
    let sum = 0;
    for (let j = i - n + 1; j <= i; j++) sum += prices[j];
    out[i] = sum / n;
  }
  return out;
}

function runBacktest(data, initialCapital) {
  const prices = data.map(d => d.close);
  const ma20 = SMA(prices, 20);

  const trades = [];
  const equity = [];
  let capital = initialCapital;
  let position = 0;
  let avgCost = 0;
  let peak = initialCapital;
  let maxDD = 0;
  let inCashDays = 0;
  let totalDays = 0;
  let holdDays = 0;

  for (let i = 20; i < data.length; i++) {
    totalDays++;
    if (!ma20[i] || !ma20[i - 1]) continue;

    const price = prices[i];
    const prevPrice = prices[i - 1];
    const aboveNow = price > ma20[i];
    const abovePrev = prevPrice > ma20[i - 1];

    // 买入：刚站上MA20
    if (position === 0 && !abovePrev && aboveNow) {
      const shares = Math.floor(capital / price / 100) * 100;
      if (shares > 0) {
        position = shares;
        avgCost = price;
        capital -= shares * price;
        trades.push({ type: 'BUY', date: data[i].date, price, shares, ma20: ma20[i].toFixed(2) });
      }
    }
    // 卖出：刚跌破MA20
    else if (position > 0 && abovePrev && !aboveNow) {
      const pnl = (price - avgCost) / avgCost * 100;
      trades.push({ type: 'SELL', date: data[i].date, price, shares: position, pnl: pnl.toFixed(2) + '%', ma20: ma20[i].toFixed(2), holdDays });
      capital += position * price;
      position = 0;
      avgCost = 0;
      holdDays = 0;
    }

    if (position > 0) holdDays++;
    else inCashDays++;

    const totalValue = capital + position * price;
    equity.push({ date: data[i].date, value: totalValue });
    if (totalValue > peak) peak = totalValue;
    const dd = (peak - totalValue) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // 平仓
  if (position > 0) {
    const lastPrice = data[data.length - 1].close;
    capital += position * lastPrice;
    trades.push({ type: 'SELL', date: data[data.length - 1].date, price: lastPrice, shares: position, reason: '回测结束', holdDays });
  }

  return { trades, equity, finalValue: capital, maxDD, inCashDays, totalDays };
}

function calcStats(equity, initialCapital, maxDD, inCashDays, totalDays) {
  const finalV = equity[equity.length - 1].value;
  const totalRet = (finalV - initialCapital) / initialCapital;
  const years = (new Date(equity[equity.length - 1].date) - new Date(equity[0].date)) / (365.25 * 864e5);
  const cagr = Math.pow(finalV / initialCapital, 1 / years) - 1;

  const rets = [];
  for (let i = 1; i < equity.length; i++) {
    rets.push((equity[i].value - equity[i - 1].value) / equity[i - 1].value);
  }
  const avgR = rets.reduce((a, b) => a + b, 0) / rets.length;
  const stdR = Math.sqrt(rets.reduce((a, b) => a + Math.pow(b - avgR, 2), 0) / rets.length);
  const annStd = stdR * Math.sqrt(252);
  const sharpe = annStd > 0 ? (cagr - 0.03) / annStd : 0;

  return { finalV, totalRet, cagr, sharpe, maxDD, years, cashRatio: inCashDays / totalDays };
}

function tradeStats(trades) {
  const sells = trades.filter(t => t.type === 'SELL' && !t.reason?.includes('回测'));
  const buys = trades.filter(t => t.type === 'BUY');
  if (sells.length === 0) return { count: buys.length, winRate: 0, avgWin: 0, avgLoss: 0, avgHoldDays: 0 };

  const pnls = sells.map(t => parseFloat(t.pnl));
  const wins = pnls.filter(p => p > 0);
  const loses = pnls.filter(p => p <= 0);
  const avgHold = sells.reduce((a, t) => a + (t.holdDays || 0), 0) / sells.length;

  return {
    count: buys.length,
    wins: wins.length, losses: loses.length,
    winRate: wins.length / sells.length,
    avgWin: wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0,
    avgLoss: loses.length > 0 ? loses.reduce((a, b) => a + b, 0) / loses.length : 0,
    avgHoldDays: avgHold.toFixed(0)
  };
}

async function main() {
  console.log('\n' + '='.repeat(70));
  console.log('   纯MA20穿越策略回测');
  console.log('   买入：价格刚站上MA20  |  卖出：价格刚跌破MA20');
  console.log('='.repeat(70) + '\n');

  const histFile = path.join(__dirname, '..', '..', 'data', 'history', 'sh000300.json');
  let data;
  try {
    data = JSON.parse(fs.readFileSync(histFile, 'utf8'));
    data = data.map(d => ({ date: d.date, open: d.open, close: d.close, high: d.high, low: d.low }));
  } catch (e) {
    console.error('❌ 读取数据失败:', e.message);
    process.exit(1);
  }
  console.log(`📥 ${data.length} 条 (${data[0].date} ~ ${data[data.length - 1].date})\n`);

  const ICAP = 1000000;
  const result = runBacktest(data, ICAP);
  const stats = calcStats(result.equity, ICAP, result.maxDD, result.inCashDays, result.totalDays);
  const ts = tradeStats(result.trades);

  // 买入持有
  const bhShares = Math.floor(ICAP / data[20].close);
  const bhFinal = bhShares * data[data.length - 1].close;
  const bhRet = (bhFinal / (bhShares * data[20].close) - 1) * 100;
  const bhCAGR = Math.pow(bhFinal / (bhShares * data[20].close), 1 / stats.years) - 1;

  console.log('┌────────────────────────┬──────────────┬──────────────┐');
  console.log('│ 指标                   │  MA20穿越    │  买入持有    │');
  console.log('├────────────────────────┼──────────────┼──────────────┤');
  console.log(`│ 期末资金               │ ¥${Math.round(stats.finalV).toLocaleString().padStart(10)}  │ ¥${Math.round(bhFinal).toLocaleString().padStart(10)}  │`);
  console.log(`│ 总收益率               │ ${stats.totalRet > 0 ? '+' : ''}${(stats.totalRet * 100).toFixed(2)}%        │ ${bhRet > 0 ? '+' : ''}${bhRet.toFixed(2)}%        │`);
  console.log(`│ 年化收益               │ ${stats.cagr > 0 ? '+' : ''}${(stats.cagr * 100).toFixed(2)}%        │ ${bhCAGR > 0 ? '+' : ''}${(bhCAGR * 100).toFixed(2)}%        │`);
  console.log(`│ 最大回撤               │ ${stats.maxDD.toFixed(2)}%        │ —            │`);
  console.log(`│ 夏普比率               │ ${stats.sharpe.toFixed(2)}         │ —            │`);
  console.log(`│ 交易次数               │ ${String(ts.count).padEnd(12)}│ 1            │`);
  console.log(`│ 胜率                   │ ${ts.winRate > 0 ? (ts.winRate * 100).toFixed(1) + '%' : '—'}        │ —            │`);
  console.log(`│ 平均盈利               │ ${ts.avgWin > 0 ? '+' + ts.avgWin.toFixed(2) + '%' : '—'}        │ —            │`);
  console.log(`│ 平均亏损               │ ${ts.avgLoss !== 0 ? ts.avgLoss.toFixed(2) + '%' : '—'}        │ —            │`);
  console.log(`│ 平均持仓天数           │ ${ts.avgHoldDays + '天'}         │ —            │`);
  console.log(`│ 空仓比例               │ ${(stats.cashRatio * 100).toFixed(1)}%        │ 0%           │`);
  console.log('└────────────────────────┴──────────────┴──────────────┘');

  // 近2年交易明细
  console.log('\n📋 近2年交易明细:');
  console.log('─'.repeat(50));
  const recent = result.trades.filter(t => new Date(t.date) > new Date('2024-04-01'));
  recent.forEach(t => {
    if (t.type === 'BUY') {
      console.log(`  🟢 买入 ${t.date}  ¥${t.price.toFixed(2)}  MA20=${t.ma20}`);
    } else {
      console.log(`  🔴 卖出 ${t.date}  ¥${t.price.toFixed(2)}  ${t.pnl || ''}  持仓${t.holdDays || '?'}天${t.reason ? ' [' + t.reason + ']' : ''}`);
    }
  });

  // 保存
  const outDir = path.join(__dirname, '..', '..', 'reviews', 'backtest');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, `ma20_pure_${new Date().toISOString().slice(0, 10)}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ stats, trades: result.trades }, null, 2));
  console.log(`\n📁 已保存: ${outFile}\n`);
}

main().catch(console.error);
