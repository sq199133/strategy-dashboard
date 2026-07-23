const fs = require('fs');
const pool = require('D:/QClaw_Trading/data/etf_pool.js');

console.log(`=== ETF标的池 v5.1（共${pool.length}只）===\n`);

pool.forEach((etf, i) => {
  const code = etf.code || '';
  const name = etf.name || '';
  const nav = etf.nav || etf.price || etf.current_nav || '-';
  const category = etf.category || etf.type || '-';
  console.log(`${String(i+1).padStart(2,'0')}. ${code}  ${name.padEnd(12,'　')}  净值:${nav}  [${category}]`);
});