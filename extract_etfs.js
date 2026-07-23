// Extract ETF pool to JSON
const fs = require('fs');
const pool = require('./data/etf_pool.js');

const etfs = pool.map(e => ({
  code: e.code,
  name: e.name,
  market: e.market,
  category: e.category
}));

console.log('Extracted: ' + etfs.length + ' ETFs');
fs.writeFileSync('./scripts/scan/etf_pool.json', JSON.stringify(etfs, null, 2), 'utf8');
console.log('Saved to etf_pool.json');
