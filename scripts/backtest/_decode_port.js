const fs = require('fs');
const buf = fs.readFileSync('D:/QClaw_Trading/scripts/backtest/_port_out.txt');
// GBK decode via iconv-lite fallback - just print as-is for now
const text = buf.toString('latin1');
const lines = text.split('\n');
// Show key sections
const keys = ['Loaded','Candidates','Selected','Common','sharpe','Sharpe','ÞVKmÓ~','ÞVKm','TÞVKm'];
for (const l of lines) {
  const stripped = l.trim();
  if (!stripped) continue;
  const pct = (stripped.match(/%/g)||[]).length;
  if (pct >= 10) continue; // progress bars
  // Look for lines with meaningful data
  if (stripped.match(/Loaded|Candidates|Selected|Common|sharpe|Sharpe|ÞVKm|g'Y/) ||
      stripped.match(/[0-9]+\.[0-9]{2,3}/) || stripped.match(/Sharpe/) ||
      stripped.match(/sz[0-9]|sh[0-9]/)) {
    process.stdout.write(stripped + '\n');
  }
}
