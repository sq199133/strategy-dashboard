// Check new ETF codes against current pool
const fs = require('fs');
const https = require('https');

// List to check
const codes = [
  '513300','513100','513650','513350','513800','008763','520580','513080',
  '513030','539003','520830','510300','520500','512290','515000','562600',
  '563210','515220','512690','159667','515100','561370','563700','512760',
  '515790','512010','006195'
];

// Get current pool codes
const pool = require('./data/etf_pool.js');
const poolCodes = new Set(pool.map(e => e.code));

const newCodes = codes.filter(c => !poolCodes.has(c));
console.log('=== Not in current pool: ' + newCodes.length + ' ===');
console.log(newCodes.join(', '));

// Get info for new codes using Promise
function getQuote(code) {
  return new Promise((resolve) => {
    const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqquote/get?_var=quote&param=' + code + ',,,,160';
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const match = data.match(/"name":"([^"]+)"/);
          resolve({ code, name: match ? match[1] : 'unknown' });
        } catch(e) {
          resolve({ code, name: 'error' });
        }
      });
    }).on('error', () => resolve({ code, name: 'network error' }));
  });
}

async function main() {
  console.log('\n=== Fetching ETF info ===');
  const results = [];
  for (const code of newCodes) {
    const info = await getQuote(code);
    results.push(info);
    console.log(info.code + ': ' + info.name);
    await new Promise(r => setTimeout(r, 100));
  }
  
  // Save to a file
  fs.writeFileSync('./check_etfs.json', JSON.stringify(results, null, 2), 'utf8');
  console.log('\nSaved to check_etfs.json');
}

main();