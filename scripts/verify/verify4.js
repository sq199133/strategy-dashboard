const fs = require('fs');
const sina = JSON.parse(fs.readFileSync('sina_etf.json', 'utf8'));
const em = JSON.parse(fs.readFileSync('etf_all_raw.json', 'utf8'));
const pool = require('./etf_pool_v4.js');

const emMap = {};
em.forEach(x => emMap[x.code] = x.size);
const poolCodes = new Set(pool.map(x => x.code));

const codes = ['159329', '159100', '159980', '159985'];
console.log('===== 4只ETF核实 =====\n');
codes.forEach(c => {
  const s = sina.find(x => x.code === c);
  const inPool = poolCodes.has(c);
  console.log(c + ':');
  console.log('  新浪名称: ' + (s ? s.name : 'N/A'));
  console.log('  EM规模: ' + (emMap[c] || 'N/A') + '亿');
  console.log('  已在池: ' + inPool);
});
