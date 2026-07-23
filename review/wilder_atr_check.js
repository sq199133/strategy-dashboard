const fs = require('fs');
const path = require('path');

// Compare ATR calculation methods for 510900
const d = JSON.parse(fs.readFileSync('D:/QClaw_Trading/data/history_long_v2/510900.json', 'utf8'));
const recs = d.records;

// Wilder ATR
function atrWilder(recs, period, idx) {
  if (idx < period) return null;
  let sum = 0;
  for (let i = 1; i <= period; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    sum += Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc));
  }
  let prevAtr = sum / period;
  for (let i = period + 1; i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    const tr = Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc));
    prevAtr = (prevAtr * (period - 1) + tr) / period;
  }
  return prevAtr;
}

// Simple ATR
function atrSimple(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    trs.push(Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)));
  }
  return trs.reduce((a,b)=>a+b,0) / trs.length;
}

// Distribution of ATR14/ATR21 for Wilder method
let cnt_wilder_085 = 0, cnt_wilder_090 = 0, cnt_wilder_095 = 0;
let cnt_simple_085 = 0;
const wilder_ratios = [];

for (let i = 50; i < recs.length; i++) { // start from idx=50 to ensure ATR is well-settled
  const w14 = atrWilder(recs, 14, i);
  const w21 = atrWilder(recs, 21, i);
  if (w14 && w21 && w21 > 0) {
    const r = w14/w21;
    wilder_ratios.push(r);
    if (r < 0.85) cnt_wilder_085++;
    if (r < 0.90) cnt_wilder_090++;
    if (r < 0.95) cnt_wilder_095++;
  }
  
  const s14 = atrSimple(recs, 14, i);
  const s21 = atrSimple(recs, 21, i);
  if (s14 && s21 && s21 > 0 && s14/s21 < 0.85) cnt_simple_085++;
}

wilder_ratios.sort((a,b)=>a-b);
const n = wilder_ratios.length;
console.log('Wilder ATR14/ATR21 stats (n=' + n + '):');
console.log('Median:', wilder_ratios[Math.floor(n/2)].toFixed(4));
console.log('5th pctile:', wilder_ratios[Math.floor(n*0.05)].toFixed(4));
console.log('1st pctile:', wilder_ratios[Math.floor(n*0.01)].toFixed(4));
console.log('< 0.85:', cnt_wilder_085, '(' + (cnt_wilder_085/n*100).toFixed(1) + '%)');
console.log('< 0.90:', cnt_wilder_090, '(' + (cnt_wilder_090/n*100).toFixed(1) + '%)');
console.log('< 0.95:', cnt_wilder_095, '(' + (cnt_wilder_095/n*100).toFixed(1) + '%)');
console.log('\nSimple ATR14/ATR21 < 0.85:', cnt_simple_085, '(' + (cnt_simple_085/n*100).toFixed(1) + '%)');
