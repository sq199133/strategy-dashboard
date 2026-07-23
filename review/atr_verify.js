const fs = require('fs');
const path = require('path');

// Verify ATR formula - check the ATR lookback
// ATR14 should use 14 TR values: (idx-13) to idx (inclusive)
// ATR21 should use 21 TR values: (idx-20) to idx (inclusive)
// Both should look back 1 extra for True Range (pc = recs[i-1].close)

const rawPool = fs.readFileSync('D:/QClaw_Trading/data/etf_pool_V1_full.json', 'utf8');
const fixedPool = rawPool.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(fixedPool).data;
const histDir = 'D:/QClaw_Trading/data/history_long_v2/';

const d = JSON.parse(fs.readFileSync(histDir + '510900.json', 'utf8'));
const recs = d.records;
console.log('ETF: 510900', 'records:', recs.length, 'first:', recs[0].w, 'last:', recs[recs.length-1].w);

// ATR formula verification for idx=30
const idx = 30;
console.log('\nATR check at idx=' + idx + ' (' + recs[idx].w + '):');
console.log('rec[idx-1]:', recs[idx-1].w, 'close:', recs[idx-1].close);
console.log('rec[idx]:', recs[idx].w, 'H:', recs[idx].high, 'L:', recs[idx].low, 'C:', recs[idx].close);

function atr_check(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    const tr = Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc));
    trs.push({i, w: recs[i].w, tr});
  }
  return trs.reduce((a,b)=>a+b.tr,0) / trs.length;
}

// Check ATR14 and ATR21 at various points in time
// Show ATR14/ATR21 ratio over first 100 records
let count_below_085 = 0, count_below_095 = 0, total = 0;
const ratios = [];
for (let i = 22; i < recs.length; i++) {
  const a14 = atr_check(recs, 14, i);
  const a21 = atr_check(recs, 21, i);
  if (a14 === null || a21 === null || a21 === 0) continue;
  total++;
  const r = a14/a21;
  ratios.push(r);
  if (r < 0.85) count_below_085++;
  if (r < 0.95) count_below_095++;
}
ratios.sort((a,b)=>a-b);
console.log('\nATR ratio stats for 510900 (n=' + total + ' weeks):');
console.log('Median:', ratios[Math.floor(ratios.length/2)].toFixed(4));
console.log('5th pctile:', ratios[Math.floor(ratios.length*0.05)].toFixed(4));
console.log('1st pctile:', ratios[Math.floor(ratios.length*0.01)].toFixed(4));
console.log('ATR_ratio < 0.85: ' + count_below_085 + ' (' + (count_below_085/total*100).toFixed(1) + '%)');
console.log('ATR_ratio < 0.95: ' + count_below_095 + ' (' + (count_below_095/total*100).toFixed(1) + '%)');

// Now show distribution at different thresholds
console.log('\nATR_ratio distribution:');
for (const t of [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05]) {
  const cnt = ratios.filter(r => r < t).length;
  console.log('  < ' + t + ': ' + cnt + ' (' + (cnt/total*100).toFixed(1) + '%)');
}
