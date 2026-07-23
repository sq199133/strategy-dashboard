const fs = require('fs');
const path = 'D:/QClaw_Trading/data';
const out = [];

const etfFiles = fs.readdirSync(path + '/history').filter(f => f.endsWith('.json'));
const etfData = {};

for (const f of etfFiles) {
  try {
    const obj = JSON.parse(fs.readFileSync(path + '/history/' + f, 'utf8'));
    const recs = obj.records || (obj['0'] ? Object.values(obj) : null);
    let records = null;
    if (Array.isArray(obj)) records = obj;
    else if (obj.records) records = obj.records;
    
    if (records && records.length > 0) {
      const code = f.replace('.json', '');
      const dates = records.map(r => r.date).filter(d => d);
      const start = dates[dates.length - 1];
      const end = dates[0];
      etfData[code] = { start, end, count: records.length };
    }
  } catch (e) { /* skip */ }
}

out.push('=== ETF History Coverage (' + Object.keys(etfData).length + ' files) ===');
Object.entries(etfData).sort((a, b) => etfData[a[0]].start.localeCompare(etfData[b[0]].start))
  .slice(0, 20).forEach(([k, v]) => {
    out.push(k + '\t' + v.start + '\t-> ' + v.end + '\t(' + v.count + ')');
  });

fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_etf_coverage.txt', out.join('\n'), 'utf8');
console.log('Done. ' + Object.keys(etfData).length + ' files analyzed');
console.log('Oldest:', Object.entries(etfData).sort((a,b)=>etfData[a[0]].start.localeCompare(etfData[b[0]].start))[0]);