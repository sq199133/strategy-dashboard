const fs = require('fs');
const raw = fs.readFileSync('D:/QClaw_Trading/data/history/sh510300.json', 'utf8');
const obj = JSON.parse(raw);
const keys = Object.keys(obj);
const out = [];
out.push('Keys: ' + keys.join(', '));
out.push('obj.info: ' + JSON.stringify(obj.info));
out.push('obj.records type: ' + typeof obj.records);
if (Array.isArray(obj.records)) out.push('obj.records length: ' + obj.records.length);
if (obj.records && obj.records.length > 0) {
  out.push('First record: ' + JSON.stringify(obj.records[0]));
  out.push('Last record: ' + JSON.stringify(obj.records[obj.records.length - 1]));
}
fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_debug_hist2.txt', out.join('\n'), 'utf8');
console.log('Done. Keys:', keys.join(', '));