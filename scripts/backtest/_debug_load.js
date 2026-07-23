const fs = require('fs');
const pool = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/scan/etf_pool.json', 'utf8'));
let out = '';
out += 'Pool type: ' + (Array.isArray(pool)) + ' ' + typeof pool + '\n';
if (Array.isArray(pool)) {
  out += 'Len: ' + pool.length + '\n';
  const c0 = pool[0];
  out += 'First item: ' + JSON.stringify(c0) + '\n';
  // Construct full code: market + code
  const code = (c0.market || 'sh') + c0.code;
  out += 'FullCode: ' + code + '\n';
  const p = 'D:/QClaw_Trading/data/history/' + code + '.json';
  out += 'Path: ' + p + '\n';
  out += 'Exists: ' + fs.existsSync(p) + '\n';
  // List first 5 history files
  const histFiles = fs.readdirSync('D:/QClaw_Trading/data/history').filter(f=>f.endsWith('.json')).slice(0, 10);
  out += 'First 10 hist files: ' + histFiles.join(', ') + '\n';
  // Try loading
  if (fs.existsSync(p)) {
    const raw = JSON.parse(fs.readFileSync(p, 'utf8'));
    const keys = Object.keys(raw);
    out += 'Keys: ' + keys.join(', ') + '\n';
    if (raw.records) {
      const rkeys = Object.keys(raw.records);
      out += 'records keys: ' + rkeys.join(', ') + '\n';
      if (raw.records.days) out += 'days length: ' + raw.records.days.length + '\n';
    }
  }
}
fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/_debug_out.txt', out, 'utf8');
