// Portfolio Backtest v1 - S1策略 + 相关性过滤 + 仓位管理
// 目标: 组合夏普>1，最大回撤<15%
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
      const keys = Object.keys(raw.records).filter(k => !isNaN(k)).sort((a, b) => a - b);
      if (keys.length > 0) return keys.map(k => raw.records[k]);
    }
  }
  return null;
}

function getClose(d) {
  return d.close || d.c || d.qfqClose || 0;
}

// Load all ETF data
const pool = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/scan/etf_pool.json', 'utf8'));
const files = fs.readdirSync(HIST).filter(f => f.endsWith('.json'));
const etfMap = {};
let loaded = 0;
let skipped = 0;

for (const entry of pool) {
  const code = ((entry.market || 'sh') + (entry.code || entry.name || '')).toLowerCase();
  const f = files.find(ff => ff.replace(/\.json$/i, '').toLowerCase() === code);
  if (!f) { skipped++; continue; }
  try {
    const raw = JSON.parse(fs.readFileSync(path.join(HIST, f), 'utf8'));
    const recs = getRecords(raw);
    if (!recs || recs.length < 120) { skipped++; continue; }
    const closes = recs.map(getClose).filter(v => v > 0);
    if (closes.length < 120) { skipped++; continue; }
    etfMap[code] = { code, name: entry.name || entry.code, closes, n: closes.length, category: entry.category || '' };
    loaded++;
  } catch (e) { skipped++; }
}

console.log(`Loaded: ${loaded} ETFs | Skipped: ${skipped}`);

// --- Helper: compute MA ---
function ma(arr, n) {
  const res = [];
  for (let i = n - 1; i < arr.length; i++) {
    let s = 0;
    for (let j = i - n + 1; j <= i; j++) s += arr[j];
    res.push(s / n);
  }
  return res;
}

// --- Helper: EMA ---
function ema(arr, n) {
  const k = 2 / (n + 1);
  const res = [arr[0]];
  for (let i = 1; i < arr.length; i++) res.push(arr[i] * k + res[i - 1] * (1 - k));
  return res;
}

// --- Helper: ATR ---
function atr(high, low, close, n) {
  const tr = [];
  for (let i = 0; i < close.length; i++) {
    const h = high[i] || close[i], l = low[i] || close[i];
    const prev = i > 0 ? close[i - 1] : close[i];
    tr.push(Math.max(h - l, Math.abs(h - prev), Math.abs(l - prev)));
  }
  return ma(tr, n);
}

// --- Helper: Pearson correlation ---
function pearsonCorr(a, b) {
  const n = Math.min(a.length, b.length);
  if (n < 20) return 0;
  let sa = 0, sb = 0, s2a = 0, s2b = 0, sab = 0;
  for (let i = 0; i < n; i++) { sa += a[i]; sb += b[i]; s2a += a[i] * a[i]; s2b += b[i] * b[i]; sab += a[i] * b[i]; }
  const num = sab - sa * sb / n;
  const den = Math.sqrt((s2a - sa * sa / n) * (s2b - sb * sb / n));
  return den === 0 ? 0 : num / den;
}

// --- Strategy S1: MA20+MACD+4%止损 ---
function backtestS1(closes) {
  const N = 20;
  const signal = [], equity = [1.0], trades = [], dailyReturns = [];
  const closeArr = closes;
  
  // MACD(12,26,9)
  const ema12 = ema(closeArr, 12);
  const ema26 = ema(closeArr, 26);
  const macdLine = ema12.map((v, i) => v - ema26[i]);
  const signalLine = ema(macdLine, 9);
  
  const ma20 = ma(closeArr, N);
  const macdOffset = closeArr.length - macdLine.length;
  const sigOffset = closeArr.length - signalLine.length;
  
  let pos = 0, entryPrice = 0, peak = 1.0;
  let prevMacdHist = 0;
  
  const startI = N; // need MA20
  for (let i = startI; i < closeArr.length; i++) {
    const macdIdx = i - macdOffset;
    const sigIdx = i - sigOffset;
    const macd = macdIdx >= 0 ? macdLine[macdIdx] : 0;
    const sig = sigIdx >= 0 ? signalLine[sigIdx] : 0;
    const prevMacd = macdIdx > 0 ? macdLine[macdIdx - 1] : 0;
    const prevSig = sigIdx > 0 ? signalLine[sigIdx - 1] : 0;
    
    // MACD金叉: macd从负转正 or macd从下穿上
    const crossUp = prevMacd < prevSig && macd > sig;
    const bullStart = macd > 0 && prevMacd <= 0;
    const bullConf = bullStart || crossUp;
    
    // MA20上方
    const maI = i - N;
    const aboveMA = closeArr[i] > ma20[maI];
    
    if (pos === 0 && bullConf && aboveMA) {
      pos = 1; entryPrice = closeArr[i];
    } else if (pos === 1) {
      const ret = (closeArr[i] - entryPrice) / entryPrice;
      const loss = ret <= -0.04;
      if (loss || (pos === 1 && prevMacd > prevSig && macd <= sig)) {
        // 止损或MACD死叉
        if (loss) {
          trades.push({ code: '', ret: -0.04, type: 'stop' });
        } else {
          trades.push({ code: '', ret: ret, type: 'exit' });
        }
        pos = 0; entryPrice = 0;
      }
    }
    
    const nav = equity[equity.length - 1];
    if (pos === 1) {
      const ret = (closeArr[i] - closeArr[i - 1]) / closeArr[i - 1];
      equity.push(nav * (1 + ret));
      dailyReturns.push(ret);
    } else {
      equity.push(nav);
      dailyReturns.push(0);
    }
  }
  
  if (equity.length < 50) return null;
  
  // Stats
  const rets = [];
  for (let i = 1; i < equity.length; i++) rets.push((equity[i] - equity[i - 1]) / equity[i - 1]);
  
  const totalReturn = equity[equity.length - 1] - 1;
  const years = equity.length / 252;
  const annualized = years > 0 ? Math.pow(1 + totalReturn, 1 / years) - 1 : 0;
  const std = Math.sqrt(252 * rets.reduce((s, r) => s + r * r, 0) / rets.length);
  const sharpe = std > 0 ? (annualized / std) : 0;
  
  // Max drawdown
  let peakE = 1, dd = 0;
  for (const e of equity) {
    if (e > peakE) peakE = e;
    dd = Math.max(dd, (peakE - e) / peakE);
  }
  
  // Win rate
  const wins = trades.filter(t => t.ret > 0).length;
  const winRate = trades.length > 0 ? wins / trades.length : 0;
  
  return { sharpe, annualized: annualized * 100, totalReturn: totalReturn * 100, dd: dd * 100, winRate, trades: trades.length, equity };
}

// --- Portfolio backtest ---
function runPortfolio(scenario) {
  const codes = Object.keys(etfMap);
  const results = [];
  
  // Step 1: Run S1 on each ETF
  for (const code of codes) {
    const etf = etfMap[code];
    const bt = backtestS1(etf.closes);
    if (!bt) continue;
    results.push({ ...etf, ...bt, dailyReturns: bt.equity.length > 1 ? (() => { const r = []; for (let i = 1; i < bt.equity.length; i++) r.push((bt.equity[i] - bt.equity[i-1]) / bt.equity[i-1]); return r; })() : [] });
  }
  
  // Filter by criteria
  const minSharpe = scenario.minSharpe || 0.3;
  const maxDD = scenario.maxDD || 50;
  const minTrades = scenario.minTrades || 3;
  const maxVol = scenario.maxVol || 50;
  
  let candidates = results.filter(r => 
    r.sharpe >= minSharpe && r.dd <= maxDD && r.trades >= minTrades && r.annualized > 0
  );
  
  console.log(`\nCandidates after filter (Sharpe>=${minSharpe}, DD<=${maxDD}%, Trades>=${minTrades}): ${candidates.length}`);
  
  if (candidates.length === 0) {
    console.log('No candidates! Relaxing filters...');
    candidates = results.filter(r => r.sharpe >= 0 && r.dd <= 60 && r.trades >= 1);
    console.log(`Relaxed: ${candidates.length} candidates`);
  }
  
  // Step 2: Correlation filter - pick diverse ETFs
  const maxCorr = scenario.maxCorr || 0.7;
  const maxPositions = scenario.maxPositions || 5;
  
  // Sort by Sharpe
  candidates.sort((a, b) => b.sharpe - a.sharpe);
  
  const selected = [];
  for (const c of candidates) {
    if (selected.length >= maxPositions) break;
    // Check correlation with already selected
    const tooCorrelated = selected.some(s => Math.abs(pearsonCorr(c.dailyReturns, s.dailyReturns)) > maxCorr);
    if (!tooCorrelated) selected.push(c);
  }
  
  console.log(`\nSelected ${selected.length} positions (maxCorr=${maxCorr}):`);
  for (const s of selected) {
    console.log(`  ${s.code} ${s.name} Sharpe=${s.sharpe.toFixed(2)} DD=${s.dd.toFixed(1)}}% Ann=${s.annualized.toFixed(1)}%`);
  }
  
  // Step 3: Equal-weight portfolio backtest
  const numPos = selected.length;
  if (numPos === 0) { console.log('No positions selected!'); return; }
  
  // Find common period (use min length)
  const minLen = Math.min(...selected.map(s => s.dailyReturns.length));
  console.log(`Common period: ${minLen} days`);
  
  // Portfolio returns = equal-weight average
  const portReturns = [];
  for (let i = 0; i < minLen; i++) {
    let r = 0;
    for (const s of selected) r += (s.dailyReturns[i] || 0) / numPos;
    portReturns.push(r);
  }
  
  // Build equity
  let portEquity = 1.0;
  const portEquityArr = [1.0];
  for (const r of portReturns) {
    portEquity *= (1 + r);
    portEquityArr.push(portEquity);
  }
  
  // Stats
  const totalRet = portEquity - 1;
  const years = minLen / 252;
  const annRet = years > 0 ? Math.pow(1 + totalRet, 1 / years) - 1 : 0;
  const std = Math.sqrt(252 * portReturns.reduce((s, r) => s + r * r, 0) / portReturns.length);
  const sharpe = std > 0 ? annRet / std : 0;
  let peakE2 = 1, maxDD2 = 0;
  for (const e of portEquityArr) {
    if (e > peakE2) peakE2 = e;
    maxDD2 = Math.max(maxDD2, (peakE2 - e) / peakE2);
  }
  
  console.log(`\n══════════════════════════════════════════════════════════`);
  console.log(`  组合回测结果`);
  console.log(`══════════════════════════════════════════════════════════`);
  console.log(`  夏普比率: ${sharpe.toFixed(3)}`);
  console.log(`  年化收益: ${(annRet * 100).toFixed(1)}%`);
  console.log(`  总收益:   ${(totalRet * 100).toFixed(1)}%`);
  console.log(`  最大回撤: ${(maxDD2 * 100).toFixed(1)}%`);
  console.log(`  持仓数:   ${numPos}`);
  console.log(`  覆盖天数: ${minLen}`);
  console.log(`  估算年数: ${years.toFixed(1)}年`);
  console.log(`══════════════════════════════════════════════════════════`);
  
  return { sharpe, annRet, totalRet, maxDD: maxDD2, selected, portEquityArr, portReturns, minLen };
}

// Run scenarios
console.log('\n══════════════════════════════════════════════════════════');
console.log('  组合策略回测 - S1(4%止损) + 相关性过滤');
console.log('══════════════════════════════════════════════════════════');

const scenarios = [
  { name: '保守型', minSharpe: 0.8, maxDD: 15, maxCorr: 0.6, maxPositions: 4 },
  { name: '平衡型', minSharpe: 0.5, maxDD: 25, maxCorr: 0.7, maxPositions: 5 },
  { name: '激进型', minSharpe: 0.3, maxDD: 40, maxCorr: 0.75, maxPositions: 6 },
];

for (const s of scenarios) {
  console.log(`\n>>> ${s.name} (Sharpe>=${s.minSharpe}, DD<=${s.maxDD}%, Corr<=${s.maxCorr}, MaxPos=${s.maxPositions})`);
  runPortfolio(s);
}
