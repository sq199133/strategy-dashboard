const https = require('https');

// 东方财富基金筛选 API - ETF列表，含跟踪指数信息
function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fund.eastmoney.com/data/etf/',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
      }
    }, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(12000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function main() {
  // 东方财富基金列表API - 按交易型开放式指数(ETF)筛选
  // fields: f12=代码,f14=名称,f152=跟踪指数,f162=规模
  var url = 'https://api.fund.eastmoney.com/FundScreeningApi/FundScreeningApi?m=1' +
    '&filter=ffundtype%3D%2703%27' +  // ETF类型
    '&bfz=0&pageIndex=1&pageSize=200' +
    '&sortColumn=SCALE&sortRule=-1' +
    '&dtype=JSON&token=70f12c2384f33dfcf0c397fc7f4f2a88';

  console.log('测试东方财富ETF列表API...\n');
  try {
    var raw = await httpGet(url);
    console.log('原始返回(前1000字):\n', raw.slice(0, 1000));
  } catch(e) {
    console.log('错误:', e.message);
  }
}
main().catch(console.error);
