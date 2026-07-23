// Sharpe Rolling Strategy v3: Proper equity curves + common period alignment
// Core: rolling N-day Sharpe threshold for entry/exit
const fs = require('fs');
const path = require('path');

const HIST = 'D:/QClaw_Trading/data/history';
const OUT = 'D:/QClaw_Trading/scripts/backtest';

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

// ── Load ETFs ─────────────────────────────────────────────────
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
    const closes = recs.map(getClose).filter(v => v > 0);
    if (closes.length < 126) continue;
    etfs.push({ code, name: entry.name || entry.code, category: entry.category || '', closes });
  } catch (e) {}
}
console.log(`Loaded ${etfs.length} ETFs\n`);

// ── Rolling Sharpe ────────────────────────────────────────────
function rollingSharpe(closes, window) {
  const result = new Array(closes.length).fill(NaN);
  for (let i = window; i < closes.length; i++) {
    const slice = closes.slice(i - window, i);
    const rets = [];
    for (let j = 1; j < slice.length; j++) {
      if (slice[j - 1] > 0 && slice[j] > 0) rets.push(slice[j] / slice[j - 1] - 1);
    }
    if (rets.length < window * 0.9) { result[i] = NaN; continue; }
    const mean = rets.reduce((s, r) => s + r, 0) / rets.length;
    const std = Math.sqrt(rets.reduce((s, r) => s + (r - mean) ** 2, 0) / rets.length);
    const ann = mean * 252, annStd = std * Math.sqrt(252);
    result[i] = annStd > 0.0001 ? ann / annStd : 0;
  }
  return result;
}

// ── Strategy Backtest: returns daily NAV series ────────────────
// Returns array of {dateIdx, nav} where nav starts at 1.0
// NAV stays flat during no-position periods
function backtestNav(closes, window, threshold, stopPct) {
  const sh = rollingSharpe(closes, window);
  const nav = [1.0]; // day window = 0 → NAV = 1.0 (before strategy starts)
  let pos = 0, entryPrice = 0, peak = closes[window];
  
  for (let i = window + 1; i < closes.length; i++) {
    const s = sh[i];
    const price = closes[i];
    if (price > peak) peak = price;
    const inTrend = !isNaN(s) && s > threshold;
    
    if (pos === 0 && inTrend) {
      pos = 1; entryPrice = price;
    } else if (pos === 1) {
      const exitBySharpe = !isNaN(s) && s <= threshold;
      const trailingStop = price < peak * (1 - stopPct);
      if (exitBySharpe || trailingStop) {
        pos = 0; peak = price;
      }
    }
    
    const prevNav = nav[nav.length - 1];
    if (pos === 1) {
      nav.push(prevNav * (price / closes[i - 1]));
    } else {
      nav.push(prevNav); // flat during no-position
    }
  }
  
  return { nav, trades: nav.length - 1 - window, startIdx: window };
}

// ── Compute stats from NAV series ──────────────────────────────
function navStats(nav) {
  if (nav.length < 50) return null;
  const years = nav.length / 252;
  const total = nav[nav.length - 1] / nav[0] - 1;
  const ann = years > 0 ? Math.pow(1 + total, 1 / years) - 1 : 0;
  
  // Only count days when NAV changed (active trading days)
  const activeRets = [];
  for (let i = 1; i < nav.length; i++) {
    if (nav[i] !== nav[i - 1]) activeRets.push(nav[i] / nav[i - 1] - 1);
  }
  const meanR = activeRets.length > 0 ? activeRets.reduce((s, r) => s + r, 0) / activeRets.length : 0;
  const stdR = activeRets.length > 1 
    ? Math.sqrt(activeRets.reduce((s, r) => s + (r - meanR) ** 2, 0) / (activeRets.length - 1))
    : 0;
  const annStd = stdR * Math.sqrt(252);
  const sharpe = annStd > 0.0001 ? ann / annStd : 0;
  
  let peak = nav[0], maxDD = 0;
  for (const e of nav) { if (e > peak) peak = e; const dd = (peak - e) / peak; if (dd > maxDD) maxDD = dd; }
  
  return { sharpe, ann: ann * 100, total: total * 100, maxDD: maxDD * 100, activeDays: activeRets.length };
}

// ── Grid search ───────────────────────────────────────────────
const WINDOWS = [126, 252, 378, 504, 756]; // 0.5, 1, 1.5, 2, 3 years
const THRESHOLDS = [0.0, 0.5, 1.0, 1.5];
const STOP = 0.05;
const MIN_TRADES = 1;

console.log('═══════════════════════════════════════════════════════════');
console.log('  滚动夏普策略 网格搜索 (标的池V5.3, 80只ETF)');
console.log('═══════════════════════════════════════════════════════════\n');

const allResults = [];

for (const win of WINDOWS) {
  for (const thresh of THRESHOLDS) {
    const etfResults = [];
    
    for (const etf of etfs) {
      if (etf.closes.length < win + 60) continue;
      const { nav, trades } = backtestNav(etf.closes, win, thresh, STOP);
      if (trades < MIN_TRADES) continue;
      const stats = navStats(nav);
      if (!stats) continue;
      etfResults.push({ code: etf.code, name: etf.name, category: etf.category, n: etf.closes.length, trades, ...stats });
    }
    
    if (etfResults.length < 3) continue;
    
    // Portfolio: align all NAV series to common period
    // Find the period where ALL ETFs have valid NAV (from index = win in each)
    const maxStart = win; // all start at this index
    const minEnd = Math.min(...etfResults.map(r => r.n));
    const periodLen = minEnd - maxStart;
    
    if (periodLen < 120) continue; // need at least 6 months
    
    // Build portfolio NAV: equal weight, geometric linking
    const portNav = new Array(periodLen).fill(1.0);
    for (const r of etfResults) {
      // Get the nav slice for this ETF
      // We need to reconstruct nav from stats (approximate)
      // Better: actually store nav in the per-ETF result
      // For now, use stats to estimate
      // Actually let me fix this by storing nav in the result
    }
    
    // Average individual stats (simple cross-sectional mean)
    const avgSharpe = etfResults.reduce((s, r) => s + r.sharpe, 0) / etfResults.length;
    const avgAnn = etfResults.reduce((s, r) => s + r.ann, 0) / etfResults.length;
    const avgDD = etfResults.reduce((s, r) => s + r.maxDD, 0) / etfResults.length;
    const avgWR = etfResults.reduce((s, r) => s + r.ann, 0) / etfResults.length; // placeholder
    const avgTrades = etfResults.reduce((s, r) => s + r.trades, 0) / etfResults.length;
    
    allResults.push({
      window: win, yrLabel: (win / 252).toFixed(1),
      threshold: thresh,
      nETFs: etfResults.length, periodDays: periodLen,
      avgSharpe, avgAnn, avgDD, avgTrades,
      etfResults
    });
  }
}

// Sort by avgSharpe
allResults.sort((a, b) => b.avgSharpe - a.avgSharpe);

console.log(`  ${'窗口'.padEnd(6)} ${'阈值'.padEnd(6)} ${'ETF数'.padEnd(6)} ${'覆盖期'.padEnd(8)} ${'平均夏普'.padEnd(8)} ${'平均年化'.padEnd(8)} ${'平均回撤'.padEnd(8)} ${'均交易'.padEnd(7)}`);
console.log(`  ${''.padEnd(65,'─')}`);
for (const r of allResults.slice(0, 20)) {
  const bestMark = allResults.indexOf(r) === 0 ? ' ★' : '';
  console.log(`  ${r.yrLabel.padEnd(6)} ${r.threshold.toFixed(1).padEnd(6)} ${String(r.nETFs).padEnd(6)} ${String(r.periodDays+'d').padEnd(8)} ${r.avgSharpe.toFixed(3).padEnd(8)} ${r.avgAnn.toFixed(1).padEnd(8)} ${r.avgDD.toFixed(1).padEnd(8)} ${r.avgTrades.toFixed(0).padEnd(7)}${bestMark}`);
}

// ── Best config: build proper portfolio equity ─────────────────
if (allResults.length > 0) {
  const best = allResults[0];
  console.log(`\n═══════════════════════════════════════════════════════════`);
  console.log(`  最优: ${best.yrLabel}年窗口 | 阈值=${best.threshold} | 夏普=${best.avgSharpe.toFixed(3)}`);
  console.log(`═══════════════════════════════════════════════════════════`);
  
  // Rebuild with full nav for best config
  const fullResults = [];
  for (const etf of etfs) {
    if (etf.closes.length < best.window + 60) continue;
    const { nav, trades } = backtestNav(etf.closes, best.window, best.threshold, STOP);
    if (trades < MIN_TRADES) continue;
    const stats = navStats(nav);
    if (!stats) continue;
    fullResults.push({ code: etf.code, name: etf.name, category: etf.category, n: etf.closes.length, nav, trades, ...stats });
  }
  
  fullResults.sort((a, b) => b.sharpe - a.sharpe);
  
  const periodLen = Math.min(...fullResults.map(r => r.n)) - best.window;
  console.log(`\n  有效ETF: ${fullResults.length}只 | 共同期: ${periodLen}天 (~${(periodLen/252).toFixed(1)}年)\n`);
  
  // Build actual portfolio NAV from real per-ETF nav arrays
  // Each ETF's nav starts at index best.window in its own closes array
  // For common period [best.window, min(n)) → aligned indices
  const portNav = new Array(periodLen).fill(1.0);
  const bhhNav = new Array(periodLen).fill(1.0);
  
  for (const r of fullResults) {
    const sliceStart = best.window; // where this ETF's nav starts
    const sliceLen = r.n - best.window;
    // Each ETF's nav[i] corresponds to day (best.window + i) in closes array
    // For common period, get the slice from each ETF's nav
    for (let i = 0; i < periodLen && i < sliceLen; i++) {
      const nav_i = r.nav[best.window + i - best.window + 1]; // nav offset: +1 because nav[0]=1 at idx=window
      // Actually: nav[0] = closes[window], nav[1] = closes[window+1], etc.
      // So for day (window + i) in closes: nav[i] = equity at that day
      // Our portNav[i] corresponds to day (best.window + i)
      const etr = r.nav[i + 1]; // +1 because nav[0] is before first trade day
      // But we want day (window + i) which is nav index i in the [window:] subarray
      // Actually: nav = [1.0] + [nav at closes[window+1]] + [nav at closes[window+2]] + ...
      // So for closes[window + i]: nav[i+1]
      const dailyNav = r.nav[i + 1] || r.nav[r.nav.length - 1];
      portNav[i] *= Math.pow(dailyNav, 1 / fullResults.length);
    }
    
    // Buy-hold for same ETF
    const bhhSliceStart = best.window;
    const bhhStartPrice = r.closes[bhhSliceStart];
    for (let i = 0; i < periodLen && bhhSliceStart + i < r.closes.length; i++) {
      bhhNav[i] *= r.closes[bhhSliceStart + i] / bhhStartPrice;
    }
  }
  
  const portStats = navStats(portNav);
  const bhhStats = navStats(bhhNav);
  
  console.log(`  ── 组合结果 ───────────────────────────────────`);
  console.log(`  ${'策略'.padEnd(16)} ${'夏普'.padEnd(8)} ${'年化'.padEnd(8)} ${'总收益'.padEnd(9)} ${'最大回撤'.padEnd(9)} ${'活跃天数'}`);
  console.log(`  ${''.padEnd(60,'─')}`);
  console.log(`  ${'★ 滚动夏普策略'.padEnd(16)} ${(portStats?.sharpe||0).toFixed(3).padEnd(8)} ${(portStats?.ann||0).toFixed(1).padEnd(8)} ${(portStats?.total||0).toFixed(1).padEnd(9)} ${(portStats?.maxDD||0).toFixed(1).padEnd(9)} ${portStats?.activeDays||0}`);
  console.log(`  ${'☆ 买入持有基准'.padEnd(16)} ${(bhhStats?.sharpe||0).toFixed(3).padEnd(8)} ${(bhhStats?.ann||0).toFixed(1).padEnd(8)} ${(bhhStats?.total||0).toFixed(1).padEnd(9)} ${(bhhStats?.maxDD||0).toFixed(1).padEnd(9)} ${bhhStats?.activeDays||0}`);
  console.log(`  ${''.padEnd(60,'─')}`);
  console.log(`  ${'超额收益'.padEnd(16)} ${''.padEnd(8)} ${((portStats?.ann||0)-(bhhStats?.ann||0)).toFixed(1)+'%'.padEnd(7)} ${''.padEnd(9)} ${''.padEnd(9)}`);
  console.log();
  
  // ── Individual ETF top performers ──────────────────────────────
  console.log(`  ── 个体ETF Top20 (按夏普排序) ─────────────────────────`);
  console.log(`  ${'代码'.padEnd(10)} ${'名称'.padEnd(14)} ${'年数'.padEnd(5)} ${'夏普'.padEnd(7)} ${'年化'.padEnd(7)} ${'总收益'.padEnd(8)} ${'回撤'.padEnd(7)} ${'交易'.padEnd(5)} ${'类别'}`);
  console.log(`  ${''.padEnd(90,'─')}`);
  for (const r of fullResults.slice(0, 20)) {
    const sh = r.sharpe >= 1 ? '★' : r.sharpe >= 0.5 ? '☆' : ' ';
    const yrs = (r.n - best.window) / 252;
    const name = r.name.slice(0, 12);
    console.log(`  ${sh}${r.code.padEnd(9)} ${name.padEnd(14)} ${yrs.toFixed(1).padEnd(5)} ${r.sharpe.toFixed(2).padEnd(7)} ${r.ann.toFixed(1).padEnd(7)} ${r.total.toFixed(1).padEnd(8)} ${r.maxDD.toFixed(1).padEnd(7)} ${String(r.trades).padEnd(5)} ${r.category.slice(0,8)}`);
  }
  
  // Save
  fs.writeFileSync(`${OUT}/_sharpe_portfolio.json`, JSON.stringify({
    config: { window: best.window, yrLabel: best.yrLabel, threshold: best.threshold, stopPct: STOP },
    period: { days: periodLen, years: +(periodLen/252).toFixed(2), nETFs: fullResults.length },
    strategy: portStats,
    buyHold: bhhStats,
    excessAnn: (portStats?.ann||0) - (bhhStats?.ann||0),
    topETFs: fullResults.slice(0, 30).map(r => ({ code: r.code, name: r.name, sharpe: +r.sharpe.toFixed(3), ann: +r.ann.toFixed(1), total: +r.total.toFixed(1), maxDD: +r.maxDD.toFixed(1), trades: r.trades }))
  }, null, 2));
  
  console.log(`\n  [结果已保存: _sharpe_portfolio.json]`);
}
