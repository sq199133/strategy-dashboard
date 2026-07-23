const fs = require('fs');
const j = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/scan/etf_pool.json', 'utf8'));

const catCount = {};
j.forEach(e => { catCount[e.category] = (catCount[e.category] || 0) + 1; });

const lines = [];
lines.push('=== ETF Pool V5.3 (' + j.length + ' ETFs) ===\n');
Object.entries(catCount).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
  lines.push(v + '  ' + k);
});

lines.push('\n=== All ETFs with Index ===');
j.forEach(e => {
  lines.push(e.market + e.code + '\t' + e.name + '\t-> ' + e.index + '\t(' + e.category + ')');
});

fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_pool_analysis.txt', lines.join('\n'), 'utf8');
console.log('Done: ' + j.length + ' ETFs, ' + Object.keys(catCount).length + ' categories');