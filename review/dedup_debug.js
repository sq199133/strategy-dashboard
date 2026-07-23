const fs = require('fs');
const path = require('path');

// Quick debug: how many ETFs pass each filter each week?
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

const MA_S = 5, MA_L = 21, ATR_RATIO = 0.85, DEV_MAX = 0.15, VOL_RATIO_MAX = 1.5;

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

function deviation(recs, idx) {
  const ma5 = ma(recs, 5, idx);
  if (ma5 === null || ma5 === 0) return null;
  return Math.abs(recs[idx].close - ma5) / ma5;
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

const stats = [];
for (const week of rebalanceWeeks) {
  let pass0 = 0, pass1 = 0, pass2 = 0, pass3 = 0, pass4 = 0, passC = 0;
  for (const etf of pool) {
    const recs = allData[etf.code];
    if (!recs) continue;
    const idx = recs.findIndex(r => r.w === week);
    if (idx < 21) continue;
    pass0++;
    const cur = recs[idx];
    const a14 = atr(recs, 14, idx);
    const a21 = atr(recs, 21, idx);
    if (a14 === null || a21 === null || a21 === 0) continue;
    if (a14 / a21 < ATR_RATIO) pass1++;
    const ma5 = ma(recs, 5, idx);
    const ma21 = ma(recs, 21, idx);
    if (!(cur.close > ma5 && ma5 > ma21)) continue;
    pass2++;
    const dev = deviation(recs, idx);
    if (dev === null || dev > DEV_MAX) continue;
    pass3++;
    const volMa10 = volMa(recs, idx);
    if (volMa10 === null || volMa10 === 0) continue;
    const vr = cur.vol / volMa10;
    if (vr > VOL_RATIO_MAX) continue;
    pass4++;
    if (isC仙人指路(recs, idx)) passC++;
  }
  if (passC > 0 || pass4 > 0) {
    stats.push({ week, pass0, pass1, pass2, pass3, pass4, passC });
  }
}

console.log('\nWeeks with at least 1 ATR-qualifying ETF:', stats.length);
stats.forEach(s => {
  console.log(s.week, 'hasData=' + s.pass0, 'atr=' + s.pass1, 'ma=' + s.pass2, 'dev=' + s.pass3, 'vol=' + s.pass4, 'C仙人=' + s.passC);
});

if (stats.length === 0) {
  console.log('\nNo weeks have qualifying ETFs!');
  // Show the top few weeks by ATR filter
  const sorted = [];
  for (const week of rebalanceWeeks) {
    let cnt = 0;
    for (const etf of pool) {
      const recs = allData[etf.code];
      if (!recs) continue;
      const idx = recs.findIndex(r => r.w === week);
      if (idx < 21) continue;
      const a14 = atr(recs, 14, idx);
      const a21 = atr(recs, 21, idx);
      if (a14 !== null && a21 !== null && a21 > 0 && a14/a21 < ATR_RATIO) cnt++;
    }
    sorted.push({week, cnt});
  }
  sorted.sort((a,b) => b.cnt - a.cnt);
  console.log('\nTop 10 weeks by ATR-qualifying ETFs:');
  sorted.slice(0, 10).forEach(s => console.log(s.week, s.cnt));
}
