const https = require('https');
const path = require('path');

// 测试3只ETF的接口
var testCodes = [
  { code: '510300', name: '沪深300ETF', market: 'SH' },
  { code: '588000', name: '科创50ETF', market: 'SH' },
  { code: '513100', name: '纳指ETF', market: 'SH' },
];

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fundf10.eastmoney.com/',
        'Accept': 'application/json'
      }
    }, (res) => {
      console.log('HTTP status:', res.statusCode);
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function main() {
  for (var t of testCodes) {
    var secid = t.market === 'SH' ? '1.' + t.code : '0.' + t.code;
    var url = 'https://push2.eastmoney.com/api/qt/ulist.np/get?' +
      'secids=' + secid +
      '&fields=f12,f14,f100,f103,f104,f105,f128,f129,f130,f131,f132' +
      '&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2';

    console.log('\n--- 测试 ' + t.code + ' (' + t.name + ') ---');
    try {
      var data = await httpGet(url);
      var j = JSON.parse(data);
      console.log('原始返回:', JSON.stringify(j, null, 2));
    } catch(e) {
      console.log('错误:', e.message);
    }
  }
}
main().catch(console.error);
