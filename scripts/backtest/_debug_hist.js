const fs = require('fs');
const path = 'D:/QClaw_Trading/data/history/sh510300.json';
const raw = fs.readFileSync(path);
const lines = raw.toString('utf8').split('\n');
const info = {};
const records = [];

for (let i = 0; i < lines.length; i++) {
  const line = lines[i].trim();
  if (!line) continue;
  try {
    const obj = JSON.parse(line);
    if (obj.info) {
      Object.assign(info, obj.info);
    } else {
      records.push(obj);
    }
  } catch (e) { break; }
}

const out = [];
out.push('File: ' + path);
out.push('Total lines: ' + lines.length);
out.push('Info: ' + JSON.stringify(info));
out.push('Records: ' + records.length);
if (records.length > 0) {
  out.push('First: ' + JSON.stringify(records[0]));
  out.push('Last: ' + JSON.stringify(records[records.length - 1]));
}
fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_debug_hist.txt', out.join('\n'), 'utf8');
console.log('Done');