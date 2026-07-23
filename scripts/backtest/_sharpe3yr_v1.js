// Backtest: 3-Year Rolling Sharpe Ratio as Core Signal
// 买入: 3年夏普 > 1
// 卖出: 3年夏普 < 1
// 回测期: ETF成立日 ~ 2025-12-31
const fs = require('fs');
const path = require('path');

const HIST = 'D:/QClaw_Trading/data/history';

// ── Data Loading ──────────────────────────────────────────────
function getRecords(raw) {
  if (!raw) return null;
  if (Array.isArray(raw)) return raw;
  if (raw.records) {
    if (Array.isArray(raw.records)) return raw.records;
    if (typeof raw.records === 'object') {
      if (raw.records.days) return raw.records.days;
      if (raw.records.qfqday) return raw.records.qfqday;
      if (raw.records.day) return raw.records.day;
      const keys = Object.keys(raw.records).filter(k => !isNaN(k)).sort((a, b) => +a - +b);
      if (keys.length > 0) return keys.map(k => raw.records[k]);
    }
  }
  return null;
}
function getClose(d) {
  return d.close || d.c || d.qfqClose || 0;
}
function getDate(d) {
  return d.date || d.d || d.day || (typeof d === 'object' ? Object.values(d)[0] : null);
}

// Load pool V5.3
const pool = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/scan/etf_pool.json', 'utf8'));
const files = fs.readdirSync(HIST).filter(f => f.endsWith('.json'));

const etfs = [];
for (const entry of pool) {
  const code = ((entry.market || 'sh') + (entry.code || '')).toLowerCase();
  const f = files.find(ff => ff.replace(/\.json$/i, '').toLowerCase() === code);
  if (!f) continue;
  try {
    const raw = JSON.parse(fs.readFileSync(path.join(HIST, f), 'utf8'));
    const recs = getRecords(raw);
    if (!recs || recs.length < 252) continue; // need at least 1 year for 3yr sharpe calc
    const closes = recs.map(getClose);
    const dates = recs.map(getDate);
    if (closes.filter(v => v > 0).length < 252) continue;
    // Filter out placeholder data (zero prices)
    if (closes.slice(0, 10).every(v => v === 0)) continue;
    etfs.push({
      code,
      name: entry.name || entry.code,
      category: entry.category || '',
      closes,
      dates,
      n: closes.length
    });
  } catch (e) {}
}

console.log(`Loaded ${etfs.length} ETFs (need ≥252 data points)\n`);

// ── Core Indicator: 3-Year Rolling Sharpe ─────────────────────
// Uses trading days (~252 days = 1 year)
const YR = 252;
const SHARPE_WINDOW = YR * 3; // 3 years

function rollingSharpe(closes, window) {
  const result = [];
  for (let i = window; i < closes.length; i++) {
    const slice = closes.slice(i - window, i);
    // Compute daily returns
    const rets = [];
    for (let j = 1; j < slice.length; j++) {
      if (slice[j - 1] > 0 && slice[j] > 0) {
        rets.push((slice[j] - slice[j - 1]) / slice[j - 1]);
      }
    }
    if (rets.length < window * 0.9) { result.push(NaN); continue; }
    const mean = rets.reduce((s, r) => s + r, 0) / rets.length;
    const var_ = rets.reduce((s, r) => s + (r - mean) ** 2, 0) / rets.length;
    const std = Math.sqrt(var_);
    if (std === 0) { result.push(0); continue; }
    const ann = mean * 252;
    const annStd = std * Math.sqrt(252);
    result.push(annStd > 0 ? ann / annStd : 0);
  }
  return result;
}

// ── Single ETF Backtest ─────────────────────────────────────────
// Strategy: 
//   - BUY when 3yr rolling Sharpe > SHARPETHRESH (default 1.0)
//   - SELL when 3yr rolling Sharpe <= SHARPETHRESH OR price drops SHARPETHRESH% from peak
//   - No position when flat
// Also: Buy-and-hold baseline
function backtestSharpe3(closes, threshold) {
  const sh = rollingSharpe(closes, SHARPE_WINDOW);
  const offset = closes.length - sh.length; // index offset for sh array access
  
  const equity = [1.0];
  const trades = [];
  let pos = 0; // 0=flat, 1=long
  let peak = closes[offset] || closes[SHARPE_WINDOW];
  let entryPrice = 0;
  let posStartIdx = 0;
  
  for (let i = SHARPE_WINDOW; i < closes.length; i++) {
    const shIdx = i - offset; // corresponding index in sh array
    const s3 = sh[shIdx];
    const price = closes[i];
    
    // Update peak
    if (price > peak) peak = price;
    
    const inTrend = !isNaN(s3) && s3 > threshold;
    
    if (pos === 0 && inTrend) {
      pos = 1; entryPrice = price; posStartIdx = i;
    } else if (pos === 1) {
      // Exit: 3yr Sharpe drops below threshold
      const exitBySharpe = !isNaN(s3) && s3 <= threshold;
      // OR: trailing stop at 5%
      const trailingStop = price < peak * 0.95;
      
      if (exitBySharpe || trailingStop) {
        const ret = (price - entryPrice) / entryPrice;
        trades.push({ 
          entry: posStartIdx, exit: i, 
          ret, 
          type: exitBySharpe ? 'sharpe' : 'stop',
          sharpeAtBuy: sh[shIdx - (i - posStartIdx)],
          sharpeAtSell: s3
        });
        pos = 0; entryPrice = 0;
        peak = price;
      }
    }
    
    // Record equity
    const prevEquity = equity[equity.length - 1];
    if (pos === 1 && equity.length > 1) {
      const dayRet = closes[i] / closes[i - 1] - 1;
      equity.push(prevEquity * (1 + dayRet));
    } else {
      equity.push(prevEquity);
    }
  }
  
  // Compute stats
  if (equity.length < 60) return null;
  const years = equity.length / 252;
  const totalRet = equity[equity.length - 1] / equity[0] - 1;
  const annRet = years > 0 ? Math.pow(1 + totalRet, 1 / years) - 1 : 0;
  
  // Daily returns for Sharpe
  const rets = [];
  for (let i = 1; i < equity.length; i++) {
    if (equity[i] !== equity[i - 1]) { // only count active days
      rets.push(equity[i] / equity[i - 1] - 1);
    }
  }
  const activeDays = rets.length;
  const meanR = rets.length > 0 ? rets.reduce((s, r) => s + r, 0) / rets.length : 0;
  const stdR = rets.length > 1 
    ? Math.sqrt(rets.reduce((s, r) => s + (r - meanR) ** 2, 0) / (rets.length - 1))
    : 0;
  const annStd = stdR * Math.sqrt(252);
  const sharpe = annStd > 0 ? annRet / annStd : 0;
  
  // Max drawdown
  let peakE = equity[0], maxDD = 0;
  for (const e of equity) {
    if (e > peakE) peakE = e;
    const dd = (peakE - e) / peakE;
    if (dd > maxDD) maxDD = dd;
  }
  
  const wins = trades.filter(t => t.ret > 0).length;
  const winRate = trades.length > 0 ? wins / trades.length : 0;
  
  return {
    sharpe, annRet: annRet * 100, totalRet: totalRet * 100,
    maxDD: maxDD * 100, winRate,
    trades: trades.length, activeDays, equity, years,
    buys: trades.filter(t => t.type === 'sharpe').length,
    stops: trades.filter(t => t.type === 'stop').length
  };
}

// ── Run Backtests ──────────────────────────────────────────────
console.log('═══════════════════════════════════════════════════════════');
console.log('  3年滚动夏普策略回测 (阈值 > 1.0)');
console.log('═══════════════════════════════════════════════════════════');

const results = [];

for (const etf of etfs) {
  const bt = backtestSharpe3(etf.closes, 1.0);
  if (!bt || bt.trades < 1) continue;
  results.push({
    code: etf.code,
    name: etf.name,
    category: etf.category,
    n: etf.n,
    years: bt.years,
    ...bt
  });
}

// Sort by Sharpe
results.sort((a, b) => b.sharpe - a.sharpe);

console.log(`\n有效ETF（含至少1笔交易）: ${results.length}/${etfs.length}\n`);

// ── Portfolio-level backtest ────────────────────────────────────
// Build period-aligned equity curves for all qualifying ETFs
// Then simulate equal-weight portfolio over common period

// Step 1: Find the longest common period across all qualifying ETFs
const minLen = Math.min(...results.map(r => r.equity.length));
console.log(`共同回测期: ${minLen} 交易日 (~${(minLen/252).toFixed(1)}年)\n`);

// Step 2: Equal-weight portfolio
const portEquity = new Array(minLen).fill(1.0);
for (const r of results) {
  const slice = r.equity.slice(0, minLen);
  for (let i = 0; i < minLen; i++) {
    portEquity[i] *= Math.pow(slice[i] / slice[0], 1 / results.length);
  }
}

// Recompute stats
const portYears = minLen / 252;
const portTotal = portEquity[portEquity.length - 1] / portEquity[0] - 1;
const portAnn = portYears > 0 ? Math.pow(1 + portTotal, 1 / portYears) - 1 : 0;
const portRets = [];
for (let i = 1; i < portEquity.length; i++) {
  const r = portEquity[i] / portEquity[i - 1] - 1;
  if (Math.abs(r) > 0.001) portRets.push(r);
}
const portMean = portRets.reduce((s, r) => s + r, 0) / portRets.length;
const portStd = portRets.length > 1 
  ? Math.sqrt(portRets.reduce((s, r) => s + (r - portMean) ** 2, 0) / (portRets.length - 1))
  : 0;
const portAnnStd = portStd * Math.sqrt(252);
const portSharpe = portAnnStd > 0 ? portAnn / portAnnStd : 0;
let portPeak = portEquity[0], portMaxDD = 0;
for (const e of portEquity) {
  if (e > portPeak) portPeak = e;
  const dd = (portPeak - e) / portPeak;
  if (dd > portMaxDD) portMaxDD = dd;
}

// Step 3: Also run buy-and-hold on same ETFs for comparison
const bhhEquity = new Array(minLen).fill(1.0);
for (const r of results) {
  const slice = r.equity.slice(0, minLen);
  for (let i = 0; i < minLen; i++) {
    bhhEquity[i] *= slice[i] / slice[0];
  }
}
const bhhTotal = bhhEquity[bhhEquity.length - 1] / bhhEquity[0] - 1;
const bhhAnn = portYears > 0 ? Math.pow(1 + bhhTotal, 1 / portYears) - 1 : 0;
const bhhRets = [];
for (let i = 1; i < bhhEquity.length; i++) {
  const r = bhhEquity[i] / bhhEquity[i - 1] - 1;
  if (Math.abs(r) > 0.0001) bhhRets.push(r);
}
const bhhMean = bhhRets.reduce((s, r) => s + r, 0) / bhhRets.length;
const bhhStd = bhhRets.length > 1 
  ? Math.sqrt(bhhRets.reduce((s, r) => s + (r - bhhMean) ** 2, 0) / (bhhRets.length - 1))
  : 0;
const bhhAnnStd = bhhStd * Math.sqrt(252);
const bhhSharpe = bhhAnnStd > 0 ? bhhAnn / bhhAnnStd : 0;
let bhhPeak = bhhEquity[0], bhhMaxDD = 0;
for (const e of bhhEquity) {
  if (e > bhhPeak) bhhPeak = e;
  const dd = (bhhPeak - e) / bhhPeak;
  if (dd > bhhMaxDD) bhhMaxDD = dd;
}

// ── Print Summary ───────────────────────────────────────────────
const line = '═══════════════════════════════════════════════════════════';
console.log(line);
console.log('  3年夏普策略 — 组合汇总');
console.log(line);
console.log(`  组合ETF数:      ${results.length} 只`);
console.log(`  共同回测期:     ${minLen}天 (${portYears.toFixed(1)}年)`);
console.log();
console.log(`  3年夏普策略:`);
console.log(`    夏普比率:     ${portSharpe.toFixed(3)}`);
console.log(`    年化收益:     ${(portAnn * 100).toFixed(1)}%`);
console.log(`    总收益:       ${(portTotal * 100).toFixed(1)}%`);
console.log(`    最大回撤:     ${(portMaxDD * 100).toFixed(1)}%`);
console.log(`    活跃交易天数: ${portRets.length}天`);
console.log();
console.log(`  买入持有基准:`);
console.log(`    夏普比率:     ${bhhSharpe.toFixed(3)}`);
console.log(`    年化收益:     ${(bhhAnn * 100).toFixed(1)}%`);
console.log(`    总收益:       ${(bhhTotal * 100).toFixed(1)}%`);
console.log(`    最大回撤:     ${(bhhMaxDD * 100).toFixed(1)}%`);
console.log();
console.log(`  策略超额收益:   ${((portAnn - bhhAnn) * 100).toFixed(1)}% / 年`);
console.log(`  夏普提升:       ${(portSharpe - bhhSharpe).toFixed(2)}`);
console.log(line);

// ── Individual ETF Results ──────────────────────────────────────
console.log('\n  个体ETF回测结果 (按夏普排序):\n');
console.log(`  ${'代码'.padEnd(10)} ${'名称'.padEnd(14)} ${'年数'.padEnd(5)} ${'夏普'.padEnd(7)} ${'年化'.padEnd(7)} ${'总收益'.padEnd(8)} ${'回撤'.padEnd(7)} ${'交易'.padEnd(5)} ${'胜率'.padEnd(6)} ${'类别'}`);
console.log(`  ${''.padEnd(100,'─')}`);
for (const r of results.slice(0, 30)) {
  const shSign = r.sharpe >= 1 ? '★' : r.sharpe >= 0.5 ? '☆' : ' ';
  const name = r.name.length > 12 ? r.name.slice(0, 11) : r.name;
  console.log(`  ${shSign}${r.code.padEnd(9)} ${name.padEnd(14)} ${r.years.toFixed(1).padEnd(5)} ${r.sharpe.toFixed(2).padEnd(7)} ${r.annRet.toFixed(1).padEnd(7)} ${r.totalRet.toFixed(1).padEnd(8)} ${r.maxDD.toFixed(1).padEnd(7)} ${String(r.trades).padEnd(5)} ${(r.winRate*100).toFixed(0).padEnd(6)} ${r.category.slice(0,8)}`);
}
console.log(`  ${''.padEnd(100,'─')}`);

// ── Save detailed results ─────────────────────────────────────
fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_sharpe3yr_results.json', 
  JSON.stringify(results.map(r => ({
    code: r.code, name: r.name, category: r.category,
    years: +r.years.toFixed(2), n: r.n,
    sharpe: +r.sharpe.toFixed(3), annRet: +r.annRet.toFixed(1),
    totalRet: +r.totalRet.toFixed(1), maxDD: +r.maxDD.toFixed(1),
    winRate: +r.winRate.toFixed(2), trades: r.trades, activeDays: r.activeDays,
    buys: r.buys, stops: r.stops
  })), null, 2));

// Portfolio summary
fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_sharpe3yr_portfolio.json', JSON.stringify({
  nETFs: results.length, commonDays: minLen, years: +portYears.toFixed(2),
  strategy: { sharpe: +portSharpe.toFixed(3), annRet: +(portAnn*100).toFixed(1), totalRet: +(portTotal*100).toFixed(1), maxDD: +(portMaxDD*100).toFixed(1) },
  buyHold: { sharpe: +bhhSharpe.toFixed(3), annRet: +(bhhAnn*100).toFixed(1), totalRet: +(bhhTotal*100).toFixed(1), maxDD: +(bhhMaxDD*100).toFixed(1) },
  excessAnn: +((portAnn - bhhAnn)*100).toFixed(1),
  sharpeImprovement: +(portSharpe - bhhSharpe).toFixed(2)
}, null, 2));

console.log('\n  [详细结果已保存: _sharpe3yr_results.json, _sharpe3yr_portfolio.json]');
