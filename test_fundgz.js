const https = require('https');

// 测试 fundgz 东方财富基金数据接口
var testCodes = ['510300', '588000', '513100', '159915', '512880'];

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://fundf10.eastmoney.com/'
      }
    }, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function main() {
  for (var code of testCodes) {
    // fundgz 接口
    var url = 'https://fundgz.1234567.com.cn/js/' + code + '.js?rt=1';
    console.log('\n--- ' + code + ' ---');
    try {
      var data = await httpGet(url);
      console.log('fundgz:', data.slice(0, 300));
    } catch(e) {
      console.log('fundgz err:', e.message);
    }

    // 东方财富基金档案接口
    var url2 = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=' + code + '&topline=10&year=&month=&rt=0.1';
    try {
      var data2 = await httpGet(url2);
      console.log('jjcc (前200字):', data2.slice(0, 200));
    } catch(e) {
      console.log('jjcc err:', e.message);
    }
  }
}
main().catch(console.error);
