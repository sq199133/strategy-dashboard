const fs = require('fs');
const path = require('path');

// Check earliest dates for all ETFs
const rawPool = fs.readFileSync('D:/QClaw_Trading/data/etf_pool_V1_full.json', 'utf8');
const fixedPool = rawPool.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(fixedPool).data;

const histDir = 'D:/QClaw_Trading/data/history_long_v2/';
const earliestByCode = {};

for (const etf of poolData) {
  const fpath = path.join(histDir, etf.code + '.json');
  if (fs.existsSync(fpath)) {
    const raw = fs.readFileSync(fpath, 'utf8');
    try {
      const d = JSON.parse(raw);
      if (d.records && d.records.length > 0) {
        const first = d.records[0];
        earliestByCode[etf.code] = { w: first.w, date: first.date, count: d.records.length };
      }
    } catch(e) {}
  }
}

// Find ETFs with data from 2014
const from2014 = Object.entries(earliestByCode).filter(([k,v]) => v.w <= '2014-W01').sort((a,b) => a[1].w.localeCompare(b[1].w));
const from2015 = Object.entries(earliestByCode).filter(([k,v]) => v.w <= '2015-W01').sort((a,b) => a[1].w.localeCompare(b[1].w));
const from2016 = Object.entries(earliestByCode).filter(([k,v]) => v.w <= '2016-W01').sort((a,b) => a[1].w.localeCompare(b[1].w));

console.log('ETFs from 2014:', from2014.length);
from2014.slice(0,10).forEach(([k,v]) => console.log(k, v.w, v.date, 'count:', v.count));
console.log('---');
console.log('ETFs from 2015:', from2015.length);
from2015.slice(0,10).forEach(([k,v]) => console.log(k, v.w, v.date, 'count:', v.count));
console.log('---');
console.log('ETFs from 2016:', from2016.length);
from2016.slice(0,10).forEach(([k,v]) => console.log(k, v.w, v.date, 'count:', v.count));

// Show distribution of earliest weeks
const byYear = {};
Object.values(earliestByCode).forEach(v => {
  const yr = v.w.slice(0,4);
  byYear[yr] = (byYear[yr] || 0) + 1;
});
console.log('\nEarliest record distribution by year:');
Object.keys(byYear).sort().forEach(y => console.log(y + ':', byYear[y]));
