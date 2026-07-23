// Fetch correct codes for the specific ETFs we need
const https = require('https');

function fetchEM(code, market) {
  const secid = market === 'SZ' ? '0.' + code : '1.' + code;
  const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&fields=f57,f58,f84,f100`;
  return new Promise((resolve) => {
    https.get(url, { timeout: 8000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch(e) { resolve(null); } });
    }).on('error', () => resolve(null));
  });
}

async function main() {
  // Codes we need to verify
  const toCheck = [
    {code:'513100', m:'SH'}, {code:'513500', m:'SH'}, {code:'513030', m:'SH'},
    {code:'512770', m:'SH'}, {code:'512290', m:'SH'}, {code:'159938', m:'SZ'},
    {code:'512220', m:'SH'}, {code:'512660', m:'SH'}, {code:'512680', m:'SH'},
    {code:'516390', m:'SH'}, {code:'515700', m:'SH'}, {code:'501009', m:'SH'},
    {code:'513090', m:'SH'}, {code:'513520', m:'SH'},
    {code:'512500', m:'SH'}, {code:'512100', m:'SH'}, {code:'159845', m:'SZ'},
  ];
  for (const item of toCheck) {
    const j = await fetchEM(item.code, item.m);
    if (j && j.data) {
      const d = j.data;
      console.log(item.code + ' ' + d.f58 + ' | 规模:' + (d.f84 ? (d.f84/1e8).toFixed(1)+'亿':'N/A') + ' | 跟踪:' + (d.f100||'N/A'));
    } else {
      console.log(item.code + ' | 无数据');
    }
    await new Promise(r => setTimeout(r, 150));
  }
}
main();
