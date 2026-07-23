// Sharpe Rolling Strategy - 3yr Rolling Sharpe as Core Signal
// Strategy: Buy when N-day rolling Sharpe > threshold; Sell when <= threshold or 5% trailing stop
// Pool: V5.3 (87 ETFs), Full history to 2025-12-31
const fs = require('fs');
const path = require('path');

const HIST = 'D:/QClaw_Trading/data/history';
const OUT  = 'D:/QClaw_Trading/scripts/backtest';

// ---- Data Helpers ----
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
      return keys.length > 0 ? keys.map(k => raw.records[k]) : null;
    }
  }
  return null;
}
function getClose(d) { return d.close || d.c || d.qfqClose || 0; }

// ---- Load ETFs ----
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
    if (!recs) continue;
    const closes = recs.map(getClose).filter(v => v > 0);
    if (closes.length < 126) continue;
    etfs.push({ code, name: entry.name || entry.code, category: entry.category || '', closes, n: closes.length });
  } catch (e) {}
}
console.log('ETF pool loaded: ' + etfs.length + ' ETFs\n');

// ---- Rolling Sharpe ----
function rollingSharpe(closes, window) {
  const out = new Array(closes.length).fill(NaN);
  for (let i = window; i < closes.length; i++) {
    const slice = closes.slice(i - window, i);
    const rets = [];
    for (let j = 1; j < slice.length; j++) {
      if (slice[j-1] > 0 && slice[j] > 0) rets.push(slice[j]/slice[j-1] - 1);
    }
    if (rets.length < window * 0.9) { out[i] = NaN; continue; }
    const mean = rets.reduce((s,r) => s+r, 0) / rets.length;
    const std  = Math.sqrt(rets.reduce((s,r) => s+(r-mean)**2, 0) / rets.length);
    const annR = mean * 252, annS = std * Math.sqrt(252);
    out[i] = annS > 1e-4 ? annR / annS : 0;
  }
  return out;
}

// ---- Backtest: returns equity curve and stats ----
function backtest(closes, window, threshold, stopPct) {
  const sh = rollingSharpe(closes, window);
  const equity = new Array(closes.length).fill(1.0); // equity[i] = NAV at closes[i]
  let pos = 0, peak = closes[window];
  
  for (let i = window + 1; i < closes.length; i++) {
    const s = sh[i];
    const price = closes[i];
    if (price > peak) peak = price;
    const inTrend = !isNaN(s) && s > threshold;
    
    if (pos === 0 && inTrend) { pos = 1; peak = price; }
    else if (pos === 1) {
      if (!isNaN(s) && s <= threshold) { pos = 0; peak = price; }
      else if (price < peak * (1 - stopPct)) { pos = 0; peak = price; }
    }
    
    equity[i] = equity[i-1] * (pos === 1 ? price / closes[i-1] : 1);
  }
  
  const tradeCount = equity.filter((v, i) => i > window && v !== equity[i-1]).length;
  return { equity, tradeCount };
}

function calcStats(equitySlice) {
  if (!equitySlice || equitySlice.length < 60) return null;
  const years = equitySlice.length / 252;
  const total = equitySlice[equitySlice.length-1] / equitySlice[0] - 1;
  const ann   = years > 0 ? Math.pow(1 + total, 1/years) - 1 : 0;
  const rets  = [];
  for (let i = 1; i < equitySlice.length; i++) {
    if (Math.abs(equitySlice[i]-equitySlice[i-1]) > 1e-5) rets.push(equitySlice[i]/equitySlice[i-1]-1);
  }
  const meanR = rets.length > 0 ? rets.reduce((s,r)=>s+r,0)/rets.length : 0;
  const stdR  = rets.length > 1 ? Math.sqrt(rets.reduce((s,r)=>s+(r-meanR)**2,0)/(rets.length-1)) : 0;
  const annS  = stdR * Math.sqrt(252);
  const sharpe = annS > 1e-4 ? ann / annS : 0;
  let peak = equitySlice[0], maxDD = 0;
  for (const e of equitySlice) { if(e>peak) peak=e; const dd=(peak-e)/peak; if(dd>maxDD) maxDD=dd; }
  return { sharpe, ann: ann*100, total: total*100, maxDD: maxDD*100, activeDays: rets.length };
}

// ---- Grid Search ----
const WINDOWS    = [126, 252, 378, 504, 756];
const THRESHOLDS = [0.0, 0.5, 1.0, 1.5, 2.0];
const STOP = 0.05;

console.log('============================================================');
console.log('  Rolling Sharpe Strategy Grid Search (V5.3, 87 ETFs)');
console.log('============================================================\n');

const gridResults = [];

for (const win of WINDOWS) {
  for (const thr of THRESHOLDS) {
    const individual = [];
    for (const etf of etfs) {
      if (etf.closes.length < win + 60) continue;
      const { equity, tradeCount } = backtest(etf.closes, win, thr, STOP);
      if (tradeCount < 1) continue;
      const stats = calcStats(equity.slice(win));
      if (!stats) continue;
      individual.push({ code: etf.code, name: etf.name, category: etf.category, n: etf.closes.length, tradeCount, ...stats });
    }
    if (individual.length < 3) continue;
    
    const avgSharpe = individual.reduce((s,r) => s+r.sharpe, 0) / individual.length;
    const avgAnn    = individual.reduce((s,r) => s+r.ann, 0) / individual.length;
    const avgDD     = individual.reduce((s,r) => s+r.maxDD, 0) / individual.length;
    const periodLen = Math.min(...individual.map(r => r.n)) - win;
    if (periodLen < 120) continue;
    
    gridResults.push({ win, yrLabel: (win/252).toFixed(1), thr, n: individual.length, periodLen, avgSharpe, avgAnn, avgDD, individual });
  }
}

gridResults.sort((a,b) => b.avgSharpe - a.avgSharpe);

console.log('Win    Thr   ETFs  Days    AvgSharpe  AvgAnn   AvgDD');
console.log('------------------------------------------------------------');
for (const r of gridResults.slice(0, 20)) {
  const star = gridResults.indexOf(r) === 0 ? ' <-- BEST' : '';
  console.log(r.yrLabel.padEnd(7) + r.thr.toFixed(1).padEnd(7) + String(r.n).padEnd(7) + String(r.periodLen+'d').padEnd(7) + r.avgSharpe.toFixed(3).padEnd(11) + r.avgAnn.toFixed(1).padEnd(9) + r.avgDD.toFixed(1) + star);
}

// ---- Best Config: Full Portfolio NAV ----
if (gridResults.length === 0) { console.log('No valid results!'); process.exit(1); }

const best = gridResults[0];
console.log('\n============================================================');
console.log('  BEST: ' + best.yrLabel + 'yr window | Thr=' + best.thr + ' | Sharpe=' + best.avgSharpe.toFixed(3));
console.log('============================================================');

const { win, thr } = best;

// Rebuild full equity for best config
const fullResults = [];
for (const etf of etfs) {
  if (etf.closes.length < win + 60) continue;
  const { equity, tradeCount } = backtest(etf.closes, win, thr, STOP);
  if (tradeCount < 1) continue;
  const stats = calcStats(equity.slice(win));
  if (!stats) continue;
  fullResults.push({ code: etf.code, name: etf.name, category: etf.category, n: etf.closes.length, closes: etf.closes, equity, tradeCount, ...stats });
}
fullResults.sort((a,b) => b.sharpe - a.sharpe);

const periodLen = Math.min(...fullResults.map(r => r.n)) - win;
console.log('Qualifying ETFs: ' + fullResults.length + ' | Common period: ' + periodLen + 'd (~' + (periodLen/252).toFixed(1) + 'yr)\n');

// Portfolio NAV: geometric linking over common period
const portNav  = new Array(periodLen).fill(1.0);
const bhhNav   = new Array(periodLen).fill(1.0);

for (const r of fullResults) {
  const slice = r.equity.slice(win, win + periodLen);
  const bhhStart = r.closes ? r.closes[win] : slice[0];
  for (let i = 0; i < periodLen && i < slice.length; i++) {
    portNav[i] *= Math.pow(slice[i], 1 / fullResults.length);
    if (r.closes && win + i < r.closes.length) {
      bhhNav[i] *= r.closes[win + i] / bhhStart;
    }
  }
}

const portStats = calcStats(portNav);
const bhhStats  = calcStats(bhhNav);

console.log('Strategy         Sharpe   Ann%     Total%   MaxDD%   ActiveDays');
console.log('------------------------------------------------------------');
const label1 = 'RollingSharpe(' + best.yrLabel + 'y|' + thr + ')';
const label2 = 'BuyAndHold';
console.log(label1.padEnd(25) + (portStats?.sharpe||0).toFixed(3).padEnd(8) + (portStats?.ann||0).toFixed(1).padEnd(9) + (portStats?.total||0).toFixed(1).padEnd(9) + (portStats?.maxDD||0).toFixed(1).padEnd(9) + (portStats?.activeDays||0));
console.log(label2.padEnd(25) + (bhhStats?.sharpe||0).toFixed(3).padEnd(8) + (bhhStats?.ann||0).toFixed(1).padEnd(9) + (bhhStats?.total||0).toFixed(1).padEnd(9) + (bhhStats?.maxDD||0).toFixed(1).padEnd(9) + (bhhStats?.activeDays||0));
console.log('------------------------------------------------------------');
console.log('Excess Ann: ' + ((portStats?.ann||0) - (bhhStats?.ann||0)).toFixed(1) + '%/yr\n');

// Individual ETF table
console.log('Code        Name           Yrs  Sharpe  Ann%    Total%  DD%    Trades  Category');
console.log('------------------------------------------------------------');
for (const r of fullResults.slice(0, 25)) {
  const star = r.sharpe >= 1 ? '*' : r.sharpe >= 0.5 ? '+' : ' ';
  const yrs = (r.n - win) / 252;
  const nm  = r.name.slice(0, 13);
  console.log(star + r.code.padEnd(11) + nm.padEnd(14) + yrs.toFixed(1).padEnd(5) + r.sharpe.toFixed(2).padEnd(8) + r.ann.toFixed(1).padEnd(8) + r.total.toFixed(1).padEnd(8) + r.maxDD.toFixed(1).padEnd(7) + String(r.tradeCount).padEnd(8) + r.category.slice(0,8));
}
console.log('------------------------------------------------------------');
console.log('(* Sharpe>=1.0, + Sharpe>=0.5)\n');

// ---- Threshold sensitivity ----
console.log('Threshold Sensitivity (Best window=' + best.yrLabel + 'yr):');
console.log('Thr   ETFs  AvgSharpe  AvgAnn%  AvgDD%');
console.log('------------------------------------');
for (const t of THRESHOLDS) {
  const sub = [];
  for (const etf of etfs) {
    if (etf.closes.length < win + 60) continue;
    const { equity, tradeCount } = backtest(etf.closes, win, t, STOP);
    if (tradeCount < 1) continue;
    const s = calcStats(equity.slice(win));
    if (!s) continue;
    sub.push(s);
  }
  if (sub.length === 0) continue;
  const avgSh = sub.reduce((s,r)=>s+r.sharpe,0)/sub.length;
  const avgAn = sub.reduce((s,r)=>s+r.ann,0)/sub.length;
  const avgDD = sub.reduce((s,r)=>s+r.maxDD,0)/sub.length;
  const flag  = t === thr ? ' <-- BEST' : '';
  console.log(t.toFixed(1).padEnd(7) + String(sub.length).padEnd(7) + avgSh.toFixed(3).padEnd(11) + avgAn.toFixed(1).padEnd(8) + avgDD.toFixed(1) + flag);
}

// Save
fs.writeFileSync(OUT + '/sharpe_rolling_results.json', JSON.stringify({
  config: { window: win, threshold: thr, stopPct: STOP },
  pool: { total: etfs.length, qualifying: fullResults.length, periodDays: periodLen, periodYears: +(periodLen/252).toFixed(2) },
  strategy: portStats,
  buyHold: bhhStats,
  excessAnn: +(portStats?.ann - bhhStats?.ann).toFixed(1),
  topETFs: fullResults.slice(0, 30).map(r => ({
    code: r.code, name: r.name, category: r.category,
    years: +((r.n-win)/252).toFixed(2),
    sharpe: +r.sharpe.toFixed(3), ann: +r.ann.toFixed(1), total: +r.total.toFixed(1),
    maxDD: +r.maxDD.toFixed(1), trades: r.tradeCount
  }))
}, null, 2));
console.log('\n[Saved: sharpe_rolling_results.json]');
