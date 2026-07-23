const fs = require('fs');
const path = require('path');

// Check ATR ratio distribution for a sample ETF
const rawPool = fs.readFileSync('D:/QClaw_Trading/data/etf_pool_V1_full.json', 'utf8');
const fixedPool = rawPool.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(fixedPool).data;
const histDir = 'D:/QClaw_Trading/data/history_long_v2/';

function atr(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    trs.push(Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)));
  }
  return trs.reduce((a,b)=>a+b,0) / trs.length;
}

// Check for first ETF with data from 2014
let sampleCode = null;
for (const etf of poolData) {
  const fpath = path.join(histDir, etf.code + '.json');
  if (fs.existsSync(fpath)) {
    const raw = fs.readFileSync(fpath, 'utf8');
    const d = JSON.parse(raw);
    if (d.records && d.records[0].w <= '2014-W01') {
      sampleCode = etf.code;
      break;
    }
  }
}

if (!sampleCode) {
  console.log('No ETF with data from 2014 found');
} else {
  const raw = fs.readFileSync(path.join(histDir, sampleCode + '.json'), 'utf8');
  const d = JSON.parse(raw);
  const recs = d.records;
  
  console.log('Sample ETF:', sampleCode, 'records:', recs.length);
  
  let count = 0, passCount = 0;
  const ratios = [];
  for (let idx = 21; idx < recs.length; idx++) {
    const r = recs[idx];
    if (r.w < '2014-W01' || r.w > '2026-W26') continue;
    count++;
    const a14 = atr(recs, 14, idx);
    const a21 = atr(recs, 21, idx);
    if (a14 === null || a21 === null || a21 === 0) continue;
    const ratio = a14 / a21;
    ratios.push(ratio);
    if (ratio < 0.85) passCount++;
  }
  
  ratios.sort((a,b) => a-b);
  console.log('Total weeks checked:', count);
  console.log('Weeks passing ATR_RATIO < 0.85:', passCount, '(' + (passCount/count*100).toFixed(1) + '%)');
  console.log('ATR ratio range:', ratios[0].toFixed(3), '~', ratios[ratios.length-1].toFixed(3));
  console.log('ATR ratio median:', ratios[Math.floor(ratios.length/2)].toFixed(3));
  console.log('ATR ratio 5th pctile:', ratios[Math.floor(ratios.length*0.05)].toFixed(3));
  console.log('ATR ratio 1st pctile:', ratios[Math.floor(ratios.length*0.01)].toFixed(3));
  
  // Count how many at various thresholds
  [0.70, 0.75, 0.80, 0.85, 0.90].forEach(t => {
    const c = ratios.filter(r => r < t).length;
    console.log('ATR_ratio < ' + t + ':', c, '(' + (c/count*100).toFixed(1) + '%)');
  });
}
