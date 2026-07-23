// Check which codes are new and need to be added
const fs = require('fs');
const path = require('path');

// Read current pool from absolute path
const poolPath = path.join(__dirname, 'data', 'etf_pool.js');
const poolCode = fs.readFileSync(poolPath, 'utf8');

// Get all existing codes
const existingCodes = new Set();
const lines = poolCode.split('\n');
for (const line of lines) {
  const match = line.match(/code:'([^']+)'/);
  if (match) existingCodes.add(match[1]);
}

// Codes to check
const codes = [
  '513300','513100','513650','513350','513800','008763','520580','513080',
  '513030','539003','520830','510300','520500','512290','515000','562600',
  '563210','515220','512690','159667','515100','561370','563700','512760',
  '515790','512010','006195'
];

const inPool = codes.filter(c => existingCodes.has(c));
const toAdd = codes.filter(c => !existingCodes.has(c));

console.log('=== Already in pool (' + inPool.length + '): ===');
console.log(inPool.join(', '));

console.log('\n=== Need to add (' + toAdd.length + '): ===');
console.log(toAdd.join(', '));

// Now fetch info for the new codes
const https = require('https');

function getQuote(code) {
  return new Promise((resolve) => {
    const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqquote/get?_var=quote&param=' + code + ',,,,160';
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          // Extract name
          const nameMatch = data.match(/"name":"([^"]+)"/);
          const name = nameMatch ? nameMatch[1] : 'unknown';
          
          resolve({ code, name });
        } catch(e) {
          resolve({ code, name: 'error' });
        }
      });
    }).on('error', () => resolve({ code, name: 'network error' }));
  });
}

async function main() {
  console.log('\n=== Fetching info for new ETFs ===');
  const results = [];
  for (const code of toAdd) {
    const info = await getQuote(code);
    results.push(info);
    console.log(info.code + ': ' + info.name);
    await new Promise(r => setTimeout(r, 100));
  }
  
  // Save to file
  fs.writeFileSync(path.join(__dirname, 'new_etfs_to_add.json'), JSON.stringify(results, null, 2), 'utf8');
  console.log('\nSaved to new_etfs_to_add.json');
}

main();