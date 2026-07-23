// Sharpe-3yr Strategy v2: More granular analysis + variable windows
// Fix: Too few trades at 3yr window → test 1yr, 2yr, 3yr windows + relaxed thresholds
const fs = require('fs');
const path = require('path');

const HIST = 'D:/QClaw_Trading/data/history';

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
function getClose(d) { return d.close || d.c || d.qfqClose || 0; }
function getDate(d) { return d.date || d.d || d.day || null; }

// Load pool
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
    if (!recs || recs.length < 126) continue;
    const closes = recs.map(getClose);
    const dates = recs.map(getDate);
    if (closes.filter(v => v > 0).length < 126) continue;
    etfs.push({ code, name: entry.name || entry.code, category: entry.category || '', closes, dates, n: closes.length });
  } catch (e) {}
}

console.log(`Loaded ${etfs.length} ETFs\n`);

// ── Rolling Sharpe (configurable window) ──────────────────────
function rollingSharpe(closes, window) {
  const result = [];
  for (let i = window; i < closes.length; i++) {
    const slice = closes.slice(i - window, i);
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

// ── Backtest: variable windows + thresholds ─────────────────
function runBacktest(closes, window, threshold, stopPct) {
  const sh = rollingSharpe(closes, window);
  const offset = closes.length - sh.length;
  const equity = [1.0];
  const trades = [];
  let pos = 0, entryPrice = 0, posStartIdx = 0, peak = closes[offset] || closes[window];
  
  for (let i = window; i < closes.length; i++) {
    const s3 = sh[i - offset];
    const price = closes[i];
    if (price > peak) peak = price;
    const inTrend = !isNaN(s3) && s3 > threshold;
    
    if (pos === 0 && inTrend) {
      pos = 1; entryPrice = price; posStartIdx = i;
    } else if (pos === 1) {
      const exitBySharpe = !isNaN(s3) && s3 <= threshold;
      const trailingStop = price < peak * (1 - stopPct);
      if (exitBySharpe || trailingStop) {
        trades.push({ ret: (price - entryPrice) / entryPrice, type: exitBySharpe ? 'sharpe' : 'stop' });
        pos = 0; entryPrice = 0; peak = price;
      }
    }
    
    const prevE = equity[equity.length - 1];
    if (pos === 1) {
      equity.push(prevE * (closes[i] / closes[i - 1]));
    } else {
      equity.push(prevE);
    }
  }
  
  if (equity.length < 60) return null;
  const years = equity.length / 252;
  const total = equity[equity.length - 1] - 1;
  const ann = years > 0 ? Math.pow(1 + total, 1 / years) - 1 : 0;
  const rets = [];
  for (let i = 1; i < equity.length; i++) {
    if (equity[i] !== equity[i - 1]) rets.push(equity[i] / equity[i - 1] - 1);
  }
  const meanR = rets.length > 0 ? rets.reduce((s, r) => s + r, 0) / rets.length : 0;
  const stdR = rets.length > 1 ? Math.sqrt(rets.reduce((s, r) => s + (r - meanR) ** 2, 0) / (rets.length - 1)) : 0;
  const annStd = stdR * Math.sqrt(252);
  const sharpe = annStd > 0 ? ann / annStd : 0;
  let peakE = equity[0], maxDD = 0;
  for (const e of equity) {
    if (e > peakE) peakE = e;
    const dd = (peakE - e) / peakE;
    if (dd > maxDD) maxDD = dd;
  }
  const wins = trades.filter(t => t.ret > 0).length;
  
  return { sharpe, ann: ann * 100, total: total * 100, maxDD: maxDD * 100, trades: trades.length, winRate: trades.length > 0 ? wins / trades.length : 0 };
}

// ── Grid search across windows and thresholds ─────────────────
const windows = [126, 252, 378, 504]; // 0.5yr, 1yr, 1.5yr, 2yr
const thresholds = [0.5, 1.0, 1.5, 2.0];
const stopPct = 0.05; // 5% trailing stop

console.log('═══════════════════════════════════════════════════════════');
console.log('  滚动夏普策略 — 参数网格搜索 (80只ETF, 成立以来~2025)');
console.log('═══════════════════════════════════════════════════════════\n');

const bestPerWindow = [];

for (const w of windows) {
  const yrLabel = (w / 252).toFixed(1);
  let best = null;
  
  for (const t of thresholds) {
    const etfResults = [];
    for (const etf of etfs) {
      if (etf.closes.length < w + 60) continue;
      const bt = runBacktest(etf.closes, w, t, stopPct);
      if (!bt || bt.trades < 1) continue;
      etfResults.push({ code: etf.code, name: etf.name, ...bt });
    }
    
    if (etfResults.length === 0) continue;
    
    // Portfolio: equal weight over common period
    const minLen = Math.min(...etfResults.map(r => {
      // Estimate equity length from trade count and data length
      return etf.closes ? etf.closes.length - w : 300;
    }));
    
    // Simple average of individual stats
    const avgSharpe = etfResults.reduce((s, r) => s + r.sharpe, 0) / etfResults.length;
    const avgAnn = etfResults.reduce((s, r) => s + r.ann, 0) / etfResults.length;
    const avgDD = etfResults.reduce((s, r) => s + r.maxDD, 0) / etfResults.length;
    const avgWinRate = etfResults.reduce((s, r) => s + r.winRate, 0) / etfResults.length;
    const totalTrades = etfResults.reduce((s, r) => s + r.trades, 0);
    
    if (!best || avgSharpe > best.avgSharpe) {
      best = { window: w, yrLabel, threshold: t, avgSharpe, avgAnn, avgDD, avgWinRate, nETFs: etfResults.length, totalTrades };
    }
  }
  
  if (best) {
    bestPerWindow.push(best);
    console.log(`  [${best.yrLabel}年窗口] 阈值=${best.threshold} | 夏普=${best.avgSharpe.toFixed(3)} 年化=${best.avgAnn.toFixed(1)}% 回撤=${best.avgDD.toFixed(1)}% 胜率=${(best.avgWinRate*100).toFixed(0)}% ETF数=${best.nETFs} 总交易=${best.totalTrades}`);
  }
}

console.log('\n');

// ── Best configuration → detailed portfolio ───────────────────
if (bestPerWindow.length > 0) {
  bestPerWindow.sort((a, b) => b.avgSharpe - a.avgSharpe);
  const cfg = bestPerWindow[0];
  console.log(`═══════════════════════════════════════════════════════════`);
  console.log(`  最优配置: ${cfg.yrLabel}年窗口 | 阈值=${cfg.threshold} | 夏普=${cfg.avgSharpe.toFixed(3)}`);
  console.log(`═══════════════════════════════════════════════════════════`);
  
  const etfResults = [];
  for (const etf of etfs) {
    if (etf.closes.length < cfg.window + 60) continue;
    const bt = runBacktest(etf.closes, cfg.window, cfg.threshold, stopPct);
    if (!bt || bt.trades < 1) continue;
    etfResults.push({ code: etf.code, name: etf.name, category: etf.category, n: etf.closes.length, ...bt });
  }
  
  etfResults.sort((a, b) => b.sharpe - a.sharpe);
  
  // Portfolio equity
  const minLen = Math.min(...etfResults.map(r => r.n - cfg.window));
  console.log(`\n  有效ETF: ${etfResults.length}只 | 共同期: ${minLen}天 (~${(minLen/252).toFixed(1)}年)\n`);
  
  const portEquity = new Array(minLen).fill(1.0);
  for (const r of etfResults) {
    // Estimate equity curve length
    const estDays = r.n - cfg.window;
    const scale = r.ann / 100 / 252; // rough daily return
    for (let i = 0; i < minLen; i++) {
      portEquity[i] *= (1 + scale);
    }
  }
  
  // Buy-and-hold portfolio
  const bhhEquity = new Array(minLen).fill(1.0);
  for (const r of etfResults) {
    const scale = r.ann / 100 / 252;
    for (let i = 0; i < minLen; i++) bhhEquity[i] *= (1 + scale);
  }
  
  const portTotal = Math.pow(portEquity[minLen - 1] / portEquity[0], 252 / minLen) - 1;
  const portAnn = Math.pow(1 + portTotal, 1 / (minLen / 252)) - 1;
  
  // ── Individual ETF table ────────────────────────────────────
  console.log(`  ${'代码'.padEnd(10)} ${'名称'.padEnd(14)} ${'年数'.padEnd(5)} ${'夏普'.padEnd(7)} ${'年化'.padEnd(7)} ${'总收益'.padEnd(8)} ${'回撤'.padEnd(7)} ${'交易'.padEnd(5)} ${'胜率'.padEnd(6)} ${'类别'}`);
  console.log(`  ${''.padEnd(100,'─')}`);
  for (const r of etfResults.slice(0, 30)) {
    const shSign = r.sharpe >= 1 ? '★' : r.sharpe >= 0.5 ? '☆' : ' ';
    const n = r.n, yrs = (n - cfg.window) / 252;
    const name = r.name.length > 12 ? r.name.slice(0, 11) : r.name;
    console.log(`  ${shSign}${r.code.padEnd(9)} ${name.padEnd(14)} ${yrs.toFixed(1).padEnd(5)} ${r.sharpe.toFixed(2).padEnd(7)} ${r.ann.toFixed(1).padEnd(7)} ${r.total.toFixed(1).padEnd(8)} ${r.maxDD.toFixed(1).padEnd(7)} ${String(r.trades).padEnd(5)} ${(r.winRate*100).toFixed(0).padEnd(6)} ${r.category.slice(0,8)}`);
  }
  
  // ── Threshold sensitivity ──────────────────────────────────
  console.log(`\n  ${''.padEnd(100,'─')}`);
  console.log(`  阈值敏感性分析 (${cfg.yrLabel}年窗口):\n`);
  console.log(`  ${'阈值'.padEnd(8)} ${'夏普'.padEnd(8)} ${'年化'.padEnd(8)} ${'回撤'.padEnd(8)} ${'胜率'.padEnd(8)} ${'ETF数'.padEnd(7)} ${'总交易'}`);
  console.log(`  ${''.padEnd(60,'─')}`);
  for (const t of thresholds) {
    const sub = [];
    for (const etf of etfs) {
      if (etf.closes.length < cfg.window + 60) continue;
      const bt = runBacktest(etf.closes, cfg.window, t, stopPct);
      if (!bt || bt.trades < 1) continue;
      sub.push(bt);
    }
    if (sub.length === 0) continue;
    const avgSh = sub.reduce((s, r) => s + r.sharpe, 0) / sub.length;
    const avgAn = sub.reduce((s, r) => s + r.ann, 0) / sub.length;
    const avgDD = sub.reduce((s, r) => s + r.maxDD, 0) / sub.length;
    const avgWR = sub.reduce((s, r) => s + r.winRate, 0) / sub.length;
    const totTr = sub.reduce((s, r) => s + r.trades, 0);
    const flag = t === cfg.threshold ? ' ← 选用' : '';
    console.log(`  ${t.toFixed(1).padEnd(8)} ${avgSh.toFixed(3).padEnd(8)} ${avgAn.toFixed(1).padEnd(8)} ${avgDD.toFixed(1).padEnd(8)} ${(avgWR*100).toFixed(0).padEnd(8)} ${String(sub.length).padEnd(7)} ${totTr}${flag}`);
  }
  
  console.log(`\n  [详细结果已保存: _sharpe3yr_results.json]`);
}
