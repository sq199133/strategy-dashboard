const fs = require('fs');
const path = require('path');

// Detailed debug: show all qualifying ETFs per week (without ATR filter)
const rawPool = fs.readFileSync('D:/QClaw_Trading/data/etf_pool_V1_full.json', 'utf8');
const fixedPool = rawPool.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(fixedPool).data;
const histDir = 'D:/QClaw_Trading/data/history_long_v2/';

const pool = poolData.map(e => ({ code: e.code, name: e.name, cat: e.category }));
const allData = {};
for (const etf of pool) {
  const fpath = path.join(histDir + etf.code + '.json');
  if (fs.existsSync(fpath)) {
    try {
      const d = JSON.parse(fs.readFileSync(fpath, 'utf8'));
      allData[etf.code] = d.records;
    } catch(e) {}
  }
}

const MA_S = 5, MA_L = 21, DEV_MAX = 0.15, VOL_RATIO_MAX = 1.5;
const C_BONUS = 0.02, B1_BONUS = 0.00;
const ATR_RATIO = 0.85;

function ma(recs, period, idx) {
  if (idx < period - 1) return null;
  let sum = 0;
  for (let i = idx - period + 1; i <= idx; i++) sum += recs[i].close;
  return sum / period;
}

function atr(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    trs.push(Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)));
  }
  return trs.reduce((a,b)=>a+b,0) / trs.length;
}

function volMa(recs, idx) {
  if (idx < 9) return null;
  let sum = 0;
  for (let i = idx - 9; i <= idx; i++) sum += recs[i].vol;
  return sum / 10;
}

function momentum(recs, idx, n) {
  if (idx < n) return null;
  return (recs[idx].close - recs[idx - n].close) / recs[idx - n].close;
}

function isC仙人指路(recs, idx) {
  if (idx < 21) return false;
  const cur = recs[idx];
  if (cur.close <= cur.open) return false;
  const body = cur.close - cur.open;
  if (body <= 0) return false;
  const upperShadow = cur.high - cur.close;
  const lowerShadow = cur.open - cur.low;
  if (upperShadow / body <= 1.0) return false;
  if (lowerShadow >= body * 0.5) return false;
  const ma5 = ma(recs, 5, idx);
  const ma21 = ma(recs, 21, idx);
  if (!(cur.close > ma5 && ma5 > ma21)) return false;
  const volMa10 = volMa(recs, idx);
  if (volMa10 === null || volMa10 === 0) return false;
  const vr = cur.vol / volMa10;
  if (vr >= 1.5 || vr <= 0.5) return false;
  if (idx < 20) return false;
  const mom20 = (cur.close - recs[idx-20].close) / recs[idx-20].close;
  if (mom20 >= 0.5) return false;
  return true;
}

function isB1红三兵(recs, idx) {
  if (idx < 2) return false;
  for (let i = 0; i < 3; i++) {
    if (recs[idx - i].close <= recs[idx - i].open) return false;
  }
  const low0 = recs[idx].low, low1 = recs[idx-1].low, low2 = recs[idx-2].low;
  if (!(low0 > low1 && low1 > low2)) return false;
  return true;
}

function deviation(recs, idx) {
  const ma5 = ma(recs, 5, idx);
  if (ma5 === null || ma5 === 0) return null;
  return Math.abs(recs[idx].close - ma5) / ma5;
}

// Generate rebalance weeks
const allWeeks = new Set();
for (const etf of pool) {
  const recs = allData[etf.code];
  if (recs) recs.forEach(r => allWeeks.add(r.w));
}
const sortedWeeks = [...allWeeks].sort().filter(w => w >= '2014-W01' && w <= '2026-W26');
const byMonth = {};
sortedWeeks.forEach(w => {
  const ym = w.slice(0, 7);
  if (!byMonth[ym] || w > byMonth[ym]) byMonth[ym] = w;
});
const rebalanceWeeks = Object.values(byMonth).sort();

console.log('Total rebalance weeks:', rebalanceWeeks.length);

// Count per week without ATR filter
let totalQualNoAtr = 0;
let totalCNoAtr = 0;
const cWeeks = [];

for (const week of rebalanceWeeks) {
  let qual = 0, cCount = 0;
  const details = [];
  for (const etf of pool) {
    const recs = allData[etf.code];
    if (!recs) continue;
    const idx = recs.findIndex(r => r.w === week);
    if (idx < 21) continue;
    const cur = recs[idx];
    const ma5 = ma(recs, 5, idx);
    const ma21 = ma(recs, 21, idx);
    if (!(cur.close > ma5 && ma5 > ma21)) continue;
    const dev = deviation(recs, idx);
    if (dev === null || dev > DEV_MAX) continue;
    const volMa10 = volMa(recs, idx);
    if (volMa10 === null || volMa10 === 0) continue;
    const vr = cur.vol / volMa10;
    if (vr > VOL_RATIO_MAX) continue;
    
    const mom1 = momentum(recs, idx, 1);
    const mom3 = momentum(recs, idx, 3);
    const mom8 = momentum(recs, idx, 8);
    if (mom1 === null || mom3 === null || mom8 === null) continue;
    
    const score = 0.4 * mom1 + 0.4 * mom3 + 0.2 * mom8;
    const cPat = isC仙人指路(recs, idx);
    const b1Pat = isB1红三兵(recs, idx);
    const adjScore = score + (cPat ? C_BONUS : 0) + (b1Pat ? B1_BONUS : 0);
    
    qual++;
    if (cPat) {
      cCount++;
      const a14 = atr(recs, 14, idx);
      const a21 = atr(recs, 21, idx);
      const atrR = (a14 && a21 && a21 > 0) ? (a14/a21) : null;
      details.push({ code: etf.code, cat: etf.cat, adjScore, cPat, atrR: atrR ? atrR.toFixed(3) : 'N/A' });
    }
  }
  totalQualNoAtr += qual;
  totalCNoAtr += cCount;
  if (cCount > 0) cWeeks.push({ week, qual, cCount, details });
}

console.log('\n=== Without ATR filter ===');
console.log('Total qual ETFs across all weeks:', totalQualNoAtr);
console.log('Total C-pattern signals:', totalCNoAtr);
console.log('\nWeeks with C仙人指路 (no ATR filter):');
cWeeks.forEach(w => {
  console.log(w.week, 'qual=' + w.qual, 'C=' + w.cCount);
  w.details.forEach(d => console.log('  ', d.code, d.cat, 'adjScore=' + d.adjScore.toFixed(4), 'ATR=' + d.atrR));
});

// Now show WITH ATR filter
console.log('\n=== With ATR filter ===');
let totalQualWithAtr = 0;
let totalCWithAtr = 0;
const cWeeksAtr = [];

for (const week of rebalanceWeeks) {
  let qual = 0, cCount = 0;
  const details = [];
  for (const etf of pool) {
    const recs = allData[etf.code];
    if (!recs) continue;
    const idx = recs.findIndex(r => r.w === week);
    if (idx < 21) continue;
    const cur = recs[idx];
    const a14 = atr(recs, 14, idx);
    const a21 = atr(recs, 21, idx);
    if (a14 === null || a21 === null || a21 === 0) continue;
    if (a14 / a21 < ATR_RATIO) {} else continue;
    const ma5 = ma(recs, 5, idx);
    const ma21 = ma(recs, 21, idx);
    if (!(cur.close > ma5 && ma5 > ma21)) continue;
    const dev = deviation(recs, idx);
    if (dev === null || dev > DEV_MAX) continue;
    const volMa10 = volMa(recs, idx);
    if (volMa10 === null || volMa10 === 0) continue;
    const vr = cur.vol / volMa10;
    if (vr > VOL_RATIO_MAX) continue;
    
    const mom1 = momentum(recs, idx, 1);
    const mom3 = momentum(recs, idx, 3);
    const mom8 = momentum(recs, idx, 8);
    if (mom1 === null || mom3 === null || mom8 === null) continue;
    
    const score = 0.4 * mom1 + 0.4 * mom3 + 0.2 * mom8;
    const cPat = isC仙人指路(recs, idx);
    const b1Pat = isB1红三兵(recs, idx);
    const adjScore = score + (cPat ? C_BONUS : 0) + (b1Pat ? B1_BONUS : 0);
    
    qual++;
    if (cPat) {
      cCount++;
      details.push({ code: etf.code, cat: etf.cat, adjScore, atrR: (a14/a21).toFixed(3), vr: vr.toFixed(3) });
    }
  }
  totalQualWithAtr += qual;
  totalCWithAtr += cCount;
  if (cCount > 0) cWeeksAtr.push({ week, qual, cCount, details });
}

console.log('Total qual ETFs across all weeks:', totalQualWithAtr);
console.log('Total C-pattern signals:', totalCWithAtr);
console.log('\nWeeks with C仙人指路 (with ATR filter):');
cWeeksAtr.forEach(w => {
  console.log(w.week, 'qual=' + w.qual, 'C=' + w.cCount);
  w.details.forEach(d => console.log('  ', d.code, d.cat, 'adjScore=' + d.adjScore.toFixed(4), 'ATR=' + d.atrR, 'volR=' + d.vr));
});
