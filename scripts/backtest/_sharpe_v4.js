// Sharpe Rolling Strategy v4: Fixed NAV alignment
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

// Rolling Sharpe
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
    result[i] = std > 0.0001 ? (mean * 252) / (std * Math.sqrt(252)) : 0;
  }
  return result;
}

// Backtest: returns daily equity series (NAV from 1.0)
function backtest(closes, window, threshold, stopPct) {
  const sh = rollingSharpe(closes, window);
  const nav = [1.0]; // nav[0] = day-before-strategy-starts, price = closes[0]
  let pos = 0, peak = closes[window];
  
  // nav[i] corresponds to closes[i] for i >= window
  // nav length: (closes.length - window) + 1
  // nav[0] = equity at closes[window-1] (flat before strategy)
  // nav[1] = equity at closes[window]
  
  const equityByDay = new Array(window).fill(1.0); // flat before strategy
  
  for (let i = window; i < closes.length; i++) {
    const s = sh[i];
    const price = closes[i];
    if (price > peak) peak = price;
    const inTrend = !isNaN(s) && s > threshold;
    
    if (pos === 0 && inTrend) { pos = 1; peak = price; }
    else if (pos === 1) {
      if (!isNaN(s) && s <= threshold) { pos = 0; peak = price; }
      else if (price < peak * (1 - stopPct)) { pos = 0; peak = price; }
    }
    
    if (pos === 1 && i > window) {
      equityByDay.push(equityByDay[equityByDay.length - 1] * (price / closes[i - 1]));
    } else {
      equityByDay.push(equityByDay[equityByDay.length - 1]);
    }
  }
  
  return { nav: equityByDay, trades: equityByDay.filter((v, i) => i > window && v !== equityByDay[i - 1]).length };
}

function navStats(nav, startIdx) {
  const slice = nav.slice(startIdx);
  if (slice.length < 60) return null;
  const years = slice.length / 252;
  const total = slice[slice.length - 1] / slice[0] - 1;
  const ann = years > 0 ? Math.pow(1 + total, 1 / years) - 1 : 0;
  const rets = [];
  for (let i = 1; i < slice.length; i++) {
    if (Math.abs(slice[i] - slice[i-1]) > 0.0001) rets.push(slice[i] / slice[i-1] - 1);
  }
  const meanR = rets.length > 0 ? rets.reduce((s, r) => s + r, 0) / rets.length : 0;
  const stdR = rets.length > 1 ? Math.sqrt(rets.reduce((s, r) => s + (r - meanR) ** 2, 0) / (rets.length - 1)) : 0;
  const annStd = stdR * Math.sqrt(252);
  const sharpe = annStd > 0.0001 ? ann / annStd : 0;
  let peak = slice[0], maxDD = 0;
  for (const e of slice) { if (e > peak) peak = e; const dd = (peak - e) / peak; if (dd > maxDD) maxDD = dd; }
  return { sharpe, ann: ann * 100, total: total * 100, maxDD: maxDD * 100, activeDays: rets.length };
}

// ── Best config: 1yr window, threshold=0 ─────────────────────
const WINDOW = 252, THRESH = 0, STOP = 0.05;

const fullResults = [];
for (const etf of etfs) {
  if (etf.closes.length < WINDOW + 60) continue;
  const { nav, trades } = backtest(etf.closes, WINDOW, THRESH, STOP);
  if (trades < 1) continue;
  const stats = navStats(nav, WINDOW);
  if (!stats) continue;
  fullResults.push({ code: etf.code, name: etf.name, category: etf.category, n: etf.closes.length, nav, trades, ...stats });
}

fullResults.sort((a, b) => b.sharpe - a.sharpe);

const periodLen = Math.min(...fullResults.map(r => r.n)) - WINDOW;
console.log(`有效ETF: ${fullResults.length}只 | 共同期: ${periodLen}天 (~${(periodLen/252).toFixed(1)}年)\n`);

// ── Build actual portfolio NAV from real per-ETF equity curves ──
// Each ETF: equity curve of length closes.length
// Strategy starts at index WINDOW
// Common period: [WINDOW, min(n)) = first periodLen entries of each ETF's post-window equity
const portNav = new Array(periodLen).fill(1.0);
const bhhNav = new Array(periodLen).fill(1.0);

for (const r of fullResults) {
  // r.nav: equity at each closes index (length = closes.length)
  // Strategy active from index WINDOW to closes.length-1
  // For common period: use nav[WINDOW .. WINDOW+periodLen-1]
  const stratSlice = r.nav.slice(WINDOW, WINDOW + periodLen);
  const bhhStart = r.closes[WINDOW];
  
  for (let i = 0; i < periodLen && i < stratSlice.length; i++) {
    // Equal-weight geometric linking
    portNav[i] *= Math.pow(stratSlice[i], 1 / fullResults.length);
    
    // Buy-hold for comparison
    if (WINDOW + i < r.closes.length) {
      bhhNav[i] *= r.closes[WINDOW + i] / bhhStart;
    }
  }
}

const portStats = navStats(portNav, 0);
const bhhStats = navStats(bhhNav, 0);

// ── Print ──────────────────────────────────────────────────────
console.log('═══════════════════════════════════════════════════════════');
console.log('  滚动夏普策略 V4 (1年窗口 | 阈值>0 | 成立以来)");
console.log('═══════════════════════════════════════════════════════════\n');
console.log(`  ── 组合汇总 (${fullResults.length}只ETF, ${(periodLen/252).toFixed(1)}年共同期) ──`);
console.log(`  ${'策略'.padEnd(16)} ${'夏普'.padEnd(8)} ${'年化'.padEnd(8)} ${'总收益'.padEnd(9)} ${'最大回撤'.padEnd(9)} ${'活跃天数'}`);
console.log(`  ${''.padEnd(60,'─')}`);
console.log(`  ${'★ 滚动夏普(1年>0)'.padEnd(16)} ${(portStats?.sharpe||0).toFixed(3).padEnd(8)} ${(portStats?.ann||0).toFixed(1).padEnd(8)} ${(portStats?.total||0).toFixed(1).padEnd(9)} ${(portStats?.maxDD||0).toFixed(1).padEnd(9)} ${portStats?.activeDays||0}`);
console.log(`  ${'☆ 买入持有基准'.padEnd(16)} ${(bhhStats?.sharpe||0).toFixed(3).padEnd(8)} ${(bhhStats?.ann||0).toFixed(1).padEnd(8)} ${(bhhStats?.total||0).toFixed(1).padEnd(9)} ${(bhhStats?.maxDD||0).toFixed(1).padEnd(9)} ${bhhStats?.activeDays||0}`);
console.log(`  ${''.padEnd(60,'─')}`);
console.log(`  ${'超额收益'.padEnd(16)} ${''.padEnd(8)} ${((portStats?.ann||0)-(bhhStats?.ann||0)).toFixed(1)+'%'.padEnd(7)}`);
console.log();

// ── Individual ETF top performers ──────────────────────────────
console.log(`  ── 个体ETF Top25 (按夏普排序) ─────────────────────────`);
console.log(`  ${'代码'.padEnd(10)} ${'名称'.padEnd(14)} ${'年数'.padEnd(5)} ${'夏普'.padEnd(7)} ${'年化'.padEnd(7)} ${'总收益'.padEnd(8)} ${'回撤'.padEnd(7)} ${'交易'.padEnd(5)} ${'类别'}`);
console.log(`  ${''.padEnd(90,'─')}`);
for (const r of fullResults.slice(0, 25)) {
  const sh = r.sharpe >= 1 ? '★' : r.sharpe >= 0.5 ? '☆' : ' ';
  const yrs = (r.n - WINDOW) / 252;
  const name = r.name.slice(0, 12);
  console.log(`  ${sh}${r.code.padEnd(9)} ${name.padEnd(14)} ${yrs.toFixed(1).padEnd(5)} ${r.sharpe.toFixed(2).padEnd(7)} ${r.ann.toFixed(1).padEnd(7)} ${r.total.toFixed(1).padEnd(8)} ${r.maxDD.toFixed(1).padEnd(7)} ${String(r.trades).padEnd(5)} ${r.category.slice(0,8)}`);
}

// ── Threshold sensitivity on best window ──────────────────────
console.log(`\n  ── 阈值敏感性 (1年窗口) ─────────────────────────────────`);
console.log(`  ${'阈值'.padEnd(7)} ${'ETF数'.padEnd(7)} ${'夏普'.padEnd(8)} ${'年化'.padEnd(8)} ${'回撤'.padEnd(8)} ${'均交易'}`);
console.log(`  ${''.padEnd(50,'─')}`);
for (const t of [0.0, 0.5, 1.0, 1.5, 2.0]) {
  const sub = [];
  for (const etf of etfs) {
    if (etf.closes.length < WINDOW + 60) continue;
    const { trades } = backtest(etf.closes, WINDOW, t, STOP);
    if (trades < 1) continue;
    const stats = navStats(backtest(etf.closes, WINDOW, t, STOP).nav, WINDOW);
    if (!stats) continue;
    sub.push(stats);
  }
  if (sub.length === 0) continue;
  const avgSh = sub.reduce((s, r) => s + r.sharpe, 0) / sub.length;
  const avgAn = sub.reduce((s, r) => s + r.ann, 0) / sub.length;
  const avgDD = sub.reduce((s, r) => s + r.maxDD, 0) / sub.length;
  const avgTr = sub.reduce((s, r) => s + r.activeDays, 0) / sub.length;
  const flag = t === THRESH ? ' ← 选用' : '';
  console.log(`  ${t.toFixed(1).padEnd(7)} ${String(sub.length).padEnd(7)} ${avgSh.toFixed(3).padEnd(8)} ${avgAn.toFixed(1).padEnd(8)} ${avgDD.toFixed(1).padEnd(8)} ${avgTr.toFixed(0)}${flag}`);
}

// ── Grid: full table (already computed in v3, re-summarize) ─────
console.log(`\n  ── 网格搜索汇总 (已验证) ───────────────────────────────`);
console.log(`  ${'窗口'.padEnd(7)} ${'阈值'.padEnd(7)} ${'ETF数'.padEnd(7)} ${'覆盖期'.padEnd(8)} ${'平均夏普'.padEnd(8)} ${'平均年化'.padEnd(8)} ${'回撤'.padEnd(7)}`);
console.log(`  ${''.padEnd(65,'─')}`);
// From v3 grid: key rows
const gridData = [
  [1.0, 0.0, 70, 258, 2.288, 62.4, 13.2],
  [0.5, 0.0, 80, 129, 1.916, 58.7, 13.3],
  [1.0, 0.5, 70, 258, 1.847, 51.6, 12.0],
  [0.5, 0.5, 80, 129, 1.445, 45.1, 13.1],
  [1.0, 1.0, 70, 258, 1.166, 35.2, 10.8],
  [0.5, 1.0, 80, 129, 0.921, 30.4, 13.3],
  [1.5, 0.0, 4,  1917, 0.741, 67.5, 43.0],
  [2.0, 0.0, 4,  1791, 0.641, 65.7, 42.6],
  [3.0, 0.0, 4,  1539, 0.525, 73.8, 43.3],
];
for (const [w, t, n, d, sh, an, dd] of gridData) {
  const bestMark = w === 1.0 && t === 0 ? ' ★' : '';
  const flag = n <= 4 ? ' ⚠样本少' : '';
  console.log(`  ${w.toFixed(1).padEnd(7)} ${t.toFixed(1).padEnd(7)} ${String(n).padEnd(7)} ${String(d+'d').padEnd(8)} ${sh.toFixed(3).padEnd(8)} ${an.toFixed(1).padEnd(8)} ${dd.toFixed(1)}${bestMark}${flag}`);
}

// Save
fs.writeFileSync(`${OUT}/_sharpe_portfolio.json`, JSON.stringify({
  config: { window: WINDOW, threshold: THRESH, stopPct: STOP, note: '阈值>0 = 任意正夏普即买入' },
  period: { days: periodLen, years: +(periodLen/252).toFixed(2), nETFs: fullResults.length },
  strategy: portStats,
  buyHold: bhhStats,
  excessAnn: +(portStats?.ann - bhhStats?.ann).toFixed(1),
  topETFs: fullResults.slice(0, 30).map(r => ({ code: r.code, name: r.name, category: r.category, sharpe: +r.sharpe.toFixed(3), ann: +r.ann.toFixed(1), total: +r.total.toFixed(1), maxDD: +r.maxDD.toFixed(1), trades: r.trades }))
}, null, 2));
console.log(`\n  [结果已保存: _sharpe_portfolio.json]`);
