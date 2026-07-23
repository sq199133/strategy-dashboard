// ATR filter threshold analysis - find the most meaningful threshold
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

function atrSimple(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    trs.push(Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)));
  }
  return trs.reduce((a,b)=>a+b,0) / trs.length;
}

// Count ATR-qualifying ETF-weeks at different thresholds
const thresholds = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20];
const counts = {};
thresholds.forEach(t => counts[t] = 0);

// Count per week how many ETFs pass ATR filter
const weekAtrCounts = {};
for (const etf of pool) {
  const recs = allData[etf.code];
  if (!recs) continue;
  for (let idx = 21; idx < recs.length; idx++) {
    const week = recs[idx].w;
    if (week < '2014-W01' || week > '2026-W26') continue;
    const a14 = atrSimple(recs, 14, idx);
    const a21 = atrSimple(recs, 21, idx);
    if (a14 === null || a21 === null || a21 === 0) continue;
    const r = a14 / a21;
    thresholds.forEach(t => {
      if (r < t) counts[t]++;
    });
    if (!weekAtrCounts[week]) weekAtrCounts[week] = { total: 0, below85: 0, below90: 0, below95: 0 };
    weekAtrCounts[week].total++;
    if (r < 0.85) weekAtrCounts[week].below85++;
    if (r < 0.90) weekAtrCounts[week].below90++;
    if (r < 0.95) weekAtrCounts[week].below95++;
  }
}

console.log('ATR-qualifying ETF-weeks at different thresholds (Simple ATR):');
thresholds.forEach(t => {
  console.log('  ATR_ratio < ' + t + ': ' + counts[t] + ' ETF-weeks (' + (counts[t]/counts[1.00]*100).toFixed(1) + '% of all)');
});

// Weeks with >= 3 ATR-qualifying ETFs
const weeks3 = {};
thresholds.forEach(t => weeks3[t] = 0);
for (const [week, data] of Object.entries(weekAtrCounts)) {
  thresholds.forEach(t => {
    const thr = parseFloat(t);
    if (data.total > 0) { // at least some data
      const belowR = thr === 0.85 ? data.below85 : thr === 0.90 ? data.below90 : thr === 0.95 ? data.below95 : 0;
      // Actually recalculate for each threshold
    }
  });
}

// Proper count of weeks with >= 3 ATR-qualifying ETFs per threshold
// (Need to redo properly)
function countWeeksWithN(threshold) {
  let weeksWith3plus = 0;
  let totalWeeks = 0;
  for (const [week, data] of Object.entries(weekAtrCounts)) {
    totalWeeks++;
    const belowR = threshold === 0.85 ? data.below85 : threshold === 0.90 ? data.below90 : threshold === 0.95 ? data.below95 : 0;
    if (belowR >= 3) weeksWith3plus++;
  }
  return { weeksWith3plus, totalWeeks };
}

console.log('\nWeeks with >= 3 ATR-qualifying ETFs:');
[0.85, 0.90, 0.95, 1.00].forEach(t => {
  const r = countWeeksWithN(t);
  console.log('  ATR_ratio < ' + t + ': ' + r.weeksWith3plus + '/' + r.totalWeeks + ' weeks');
});

// Average ATR-qualifying ETFs per week
console.log('\nAverage ATR-qualifying ETFs per week:');
const avgByThreshold = {};
for (const t of [0.85, 0.90, 0.95, 1.00]) {
  let sum = 0, cnt = 0;
  for (const [week, data] of Object.entries(weekAtrCounts)) {
    const belowR = t === 0.85 ? data.below85 : t === 0.90 ? data.below90 : t === 0.95 ? data.below95 : 0;
    sum += belowR;
    cnt++;
  }
  avgByThreshold[t] = cnt > 0 ? sum / cnt : 0;
  console.log('  ATR_ratio < ' + t + ': avg=' + avgByThreshold[t].toFixed(1) + ' per week');
}
