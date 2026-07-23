// Find 159681 using working HTTP endpoints
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

function fetch(url) {
  return new Promise(resolve => {
    const mod = url.startsWith('https') ? https : http;
    const headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'};
    if (url.includes('sina')) headers['Referer'] = 'http://finance.sina.com.cn';
    mod.get(url, {headers}, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
    }).on('error', () => resolve(''));
  });
}

async function main() {
  // 1. Sina hq for 159681 (SZ)
  console.log('=== Sina SZ159681 ===');
  const r1 = await fetch('http://hq.sinajs.cn/list=sz159681');
  console.log(r1);
  
  await new Promise(r=>setTimeout(r,300));
  
  // 2. Sina hq for SH 159681
  console.log('\n=== Sina SH159681 ===');
  const r2 = await fetch('http://hq.sinajs.cn/list=sh159681');
  console.log(r2);
  
  await new Promise(r=>setTimeout(r,300));
  
  // 3. East Money via HTTP (pingzhongdata page)
  console.log('\n=== EM pingzhongdata 159681 ===');
  const r3 = await fetch('http://fundgz.1234567.com.cn/js/159681.js?rt=1');
  console.log('EM fundgz:', r3);
  
  await new Promise(r=>setTimeout(r,300));
  
  // 4. Search for 创业板50 in Sina ETF list
  console.log('\n=== All 创业板 in Sina ETF list ===');
  const sina = JSON.parse(fs.readFileSync(path.join(__dirname,'sina_etf.json'),'utf8'));
  const cyb = sina.filter(e => /创业板/.test(e.name));
  cyb.forEach(e => console.log(e.code+' '+e.name));
  
  // 5. All 159xxx ETFs
  console.log('\n=== All 159xxx ETFs in Sina ===');
  const all159 = sina.filter(e => e.code.startsWith('159'));
  all159.forEach(e => console.log(e.code+' '+e.name));
}
main();
