// Extract ETF data from jijindou by using their API
// Try to find the API endpoint the website uses
const https = require('https');

async function fetchJijindou(category, page) {
  // Try the common API pattern
  const url = `https://www.jijindou.com/api/etf/list?category=${category}&page=${page}&max_scale=1&core_index=1&optcheck=1&size=20`;
  return new Promise((resolve, reject) => {
    https.get(url, { timeout: 8000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch(e) { resolve(data.substring(0, 500)); }
      });
    }).on('error', e => resolve('error: ' + e.message));
  });
}

// Try different API patterns
async function main() {
  // Pattern 1
  console.log('Pattern 1: /api/etf/list');
  let r = await fetchJijindou('all', 1);
  console.log(typeof r === 'string' ? r : JSON.stringify(r).substring(0, 300));
  
  // Try the East Money ETF list API as alternative
  console.log('\n--- East Money ETF screener ---');
  const emUrl = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20,f115';
  const r2 = await new Promise((resolve) => {
    https.get(emUrl, { timeout: 10000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch(e) { resolve(null); } });
    }).on('error', () => resolve(null));
  });
  if (r2 && r2.data && r2.data.diff) {
    console.log('Found ' + r2.data.total + ' ETFs, showing first 20:');
    r2.data.diff.forEach((d, i) => {
      console.log((i+1) + '. ' + d.f12 + ' ' + d.f14 + ' 价=' + d.f2 + ' 涨=' + d.f3 + '% 规模=' + (d.f20 ? (d.f20/1e8).toFixed(1) + '亿' : 'N/A'));
    });
  }
}
main();
