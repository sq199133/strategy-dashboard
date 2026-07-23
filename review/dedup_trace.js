// Minimal trace backtest to find where signals go
const fs = require('fs');
const path = require('path');

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

const ATR_RATIO = 0.85;
const MA_S = 5, MA_L = 21, DEV_MAX = 0.15, VOL_RATIO_MAX = 1.5;
const START_W = '2014-W01', END_W = '2026-W26';

function ma(recs, period, idx) {
  if (idx < period - 1) return null;
  let sum = 0;
  for (let i = idx - period + 1; i <= idx; i++) sum += recs[i].close;
  return sum / period;
}

function atrSimple(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    trs.push(Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)));
  }
  return trs.reduce((a,b)=>a+b,0) / trs.length;
}

function volMa10(recs, idx) {
  if (idx < 9) return null;
  let sum = 0;
  for (let i = idx - 9; i <= idx; i++) sum += recs[i].vol;
  return sum / 10;
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
  const volMa10_val = volMa10(recs, idx);
  if (volMa10_val === null || volMa10_val === 0) return false;
  const vr = cur.vol / volMa10_val;
  if (vr >= 1.5 || vr <= 0.5) return false;
  if (idx < 20) return false;
  const mom20 = (cur.close - recs[idx-20].close) / recs[idx-20].close;
  if (mom20 >= 0.5) return false;
  return true;
}

// Get rebalance weeks
const allWeeks = new Set();
for (const etf of pool) {
  const recs = allData[etf.code];
  if (recs) recs.forEach(r => allWeeks.add(r.w));
}
const sortedWeeks = [...allWeeks].sort().filter(w => w >= START_W && w <= END_W);
const byMonth = {};
sortedWeeks.forEach(w => {
  const ym = w.slice(0, 7);
  if (!byMonth[ym] || w > byMonth[ym]) byMonth[ym] = w;
});
const rebalanceWeeks = Object.values(byMonth).sort();

// Test: for 2023-W09, what does the backtest find?
const testWeek = '2023-W09';
console.log('Testing week:', testWeek);
console.log('rebalanceWeeks includes', testWeek + ':', rebalanceWeeks.includes(testWeek));

// Find which ETF has 2023-W09 and what its index is
for (const etf of pool) {
  const recs = allData[etf.code];
  if (!recs) continue;
  const idx = recs.findIndex(r => r.w === testWeek);
  if (idx >= 21) {
    const cur = recs[idx];
    const ma5 = ma(recs, 5, idx);
    const ma21 = ma(recs, 21, idx);
    const a14 = atrSimple(recs, 14, idx);
    const a21 = atrSimple(recs, 21, idx);
    if (a14 && a21 && a21 > 0) {
      const atrPass = !(a14 / a21 < ATR_RATIO);
      const maPass = cur.close > ma5 && ma5 > ma21;
      if (atrPass && maPass) {
        const volMa10_val = volMa10(recs, idx);
        const vr = volMa10_val ? cur.vol / volMa10_val : 999;
        const dev = ma5 ? Math.abs(cur.close - ma5) / ma5 : 999;
        const cPat = isC仙人指路(recs, idx);
        console.log('  ', etf.code, etf.cat, 'idx=' + idx, 
          'ATR=' + (a14/a21).toFixed(3), 'atrPass=' + atrPass, 
          'maPass=' + maPass, 'dev=' + dev.toFixed(3), 'vr=' + vr.toFixed(3), 'C=' + cPat);
      }
    }
  }
}

// Also check 2021-W09
console.log('\nTesting week: 2021-W09');
const testWeek2 = '2021-W09';
for (const etf of pool) {
  const recs = allData[etf.code];
  if (!recs) continue;
  const idx = recs.findIndex(r => r.w === testWeek2);
  if (idx >= 21) {
    const cur = recs[idx];
    const ma5 = ma(recs, 5, idx);
    const ma21 = ma(recs, 21, idx);
    const a14 = atrSimple(recs, 14, idx);
    const a21 = atrSimple(recs, 21, idx);
    if (a14 && a21 && a21 > 0) {
      const atrPass = !(a14 / a21 < ATR_RATIO);
      const maPass = cur.close > ma5 && ma5 > ma21;
      if (atrPass && maPass) {
        const volMa10_val = volMa10(recs, idx);
        const vr = volMa10_val ? cur.vol / volMa10_val : 999;
        const cPat = isC仙人指路(recs, idx);
        console.log('  ', etf.code, etf.cat, 'idx=' + idx, 
          'ATR=' + (a14/a21).toFixed(3), 'atrPass=' + atrPass,
          'vr=' + vr.toFixed(3), 'C=' + cPat);
      }
    }
  }
}

// Count qualifying ETFs in each rebalance week
console.log('\nQualifying ETF count per rebalance week (with ATR filter):');
for (const week of rebalanceWeeks) {
  let qualCount = 0;
  for (const etf of pool) {
    const recs = allData[etf.code];
    if (!recs) continue;
    const idx = recs.findIndex(r => r.w === week);
    if (idx < 21) continue;
    const cur = recs[idx];
    const ma5 = ma(recs, 5, idx);
    const ma21 = ma(recs, 21, idx);
    const a14 = atrSimple(recs, 14, idx);
    const a21 = atrSimple(recs, 21, idx);
    const volMa10_val = volMa10(recs, idx);
    if (a14 === null || a21 === null || a21 === 0 || ma5 === null || ma21 === null || volMa10_val === null) continue;
    if (a14 / a21 < ATR_RATIO) continue; // ATR filter
    if (!(cur.close > ma5 && ma5 > ma21)) continue;
    const dev = ma5 ? Math.abs(cur.close - ma5) / ma5 : 999;
    if (dev > DEV_MAX) continue;
    const vr = cur.vol / volMa10_val;
    if (vr > VOL_RATIO_MAX) continue;
    qualCount++;
  }
  if (qualCount >= 3) {
    console.log('  ' + week + ': qual=' + qualCount);
  }
}
