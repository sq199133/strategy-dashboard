// Verify ALL codes in our current etf_pool.json and get their actual names + sizes
const fs = require('fs');
const path = require('path');
const https = require('https');

const pool = JSON.parse(fs.readFileSync(path.join(__dirname, 'etf_pool.json'), 'utf8'));

function fetchEM(code, market) {
  const secid = market === 'SZ' ? '0.' + code : '1.' + code;
  const url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=' + secid + '&fields=f57,f58,f84,f116,f117';
  return new Promise((resolve) => {
    https.get(url, { timeout: 8000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch(e) { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

async function main() {
  console.log('验证 ' + pool.length + ' 只ETF的代码与名称...\n');
  var errors = [];
  for (var i = 0; i < pool.length; i++) {
    var etf = pool[i];
    var j = await fetchEM(etf.code, etf.market);
    if (j && j.data) {
      var actualName = j.data.f58;
      var size = j.data.f84 ? (j.data.f84 / 1e8).toFixed(1) : 'N/A';
      var match = actualName.includes(etf.name.substring(0, 4)) || etf.name.includes(actualName.substring(0, 4));
      var flag = match ? '✅' : '❌ 名称不符';
      console.log(etf.code + ' | 池子: ' + etf.name + ' | 实际: ' + actualName + ' | 规模: ' + size + '亿 | ' + flag);
      if (!match) {
        errors.push({ code: etf.code, pool_name: etf.name, actual_name: actualName, size: size });
      }
    } else {
      console.log(etf.code + ' | ' + etf.name + ' | ❌ 无法获取数据');
      errors.push({ code: etf.code, pool_name: etf.name, actual_name: 'NO DATA', size: 0 });
    }
    await new Promise(r => setTimeout(r, 200));
  }
  
  if (errors.length > 0) {
    console.log('\n========== 名称不符汇总 ==========');
    errors.forEach(e => {
      console.log(e.code + ': 池子写的是"' + e.pool_name + '"，实际是"' + e.actual_name + '"(规模' + e.size + '亿)');
    });
  }
}
main();
