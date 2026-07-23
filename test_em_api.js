const https = require('https');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fundf10.eastmoney.com/',
        'Accept': '*/*'
      }
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function testAPIs() {
  var code = '510300';

  // API 1: 基金持仓 (结构化JSON)
  console.log('--- API1: 东方财富基金持仓 ---');
  try {
    var url = 'https://api.fund.eastmoney.com/F10/FPJZ?callback=&fundCode=' + code + '&year=&month=&day=&pageIndex=1&pageSize=10&type=1';
    var r = await httpGet(url);
    console.log(r.slice(0, 500));
  } catch(e) { console.log('err:', e.message); }

  await new Promise(r=>setTimeout(r,300));

  // API 2: 基金基本信息(含跟踪指数)
  console.log('\n--- API2: 基金基本信息 ---');
  try {
    var url2 = 'https://fundgz.1234567.com.cn/js/' + code + '.js?rt=1';
    var r2 = await httpGet(url2);
    console.log(r2.slice(0, 300));
  } catch(e) { console.log('err:', e.message); }

  await new Promise(r=>setTimeout(r,300));

  // API 3: fundF10Sir (跟踪指数)
  console.log('\n--- API3: FundF10Sir ---');
  try {
    var url3 = 'https://emapi.eastmoney.com/F10/FundF10Sir?callback=&action=1&client=web_bd&token=&appsecid=&version=&osv=Windows+10&deviceid=&id=' + code + '&type=1';
    var r3 = await httpGet(url3);
    console.log(r3.slice(0, 600));
  } catch(e) { console.log('err:', e.message); }

  await new Promise(r=>setTimeout(r,300));

  // API 4: 基金档案-跟踪指数
  console.log('\n--- API4: 基金档案 ---');
  try {
    var url4 = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=' + code + '&topline=10&year=&month=&rt=0.1';
    var r4 = await httpGet(url4);
    // 解析HTML中的内容
    var match = r4.match(/var apidata=\{[^}]+content:"([^"]+)"/);
    if (match) {
      var content = match[1].replace(/\\n/g,' ').replace(/\\"/g,'"');
      console.log('持仓内容:', content.slice(0, 500));
    } else {
      console.log('原始:', r4.slice(0, 400));
    }
  } catch(e) { console.log('err:', e.message); }

  await new Promise(r=>setTimeout(r,300));

  // API 5: 新浪财经ETF信息
  console.log('\n--- API5: 新浪财经ETF持仓 ---');
  try {
    var url5 = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount?node=hs_etf';
    var r5 = await httpGet(url5);
    console.log(r5.slice(0, 300));
  } catch(e) { console.log('err:', e.message); }

  await new Promise(r=>setTimeout(r,300));

  // API 6: 天天基金ETF跟踪指数 (尝试另一个端点)
  console.log('\n--- API6: 天天基金ETF列表 ---');
  try {
    var url6 = 'https://dcfm.eastmoney.com/em_mutualfund/MutualFundSearchService/NewFundSearch?MType=1&pageIndex=1&pageSize=20&sortColumn=NetSize&sort=desc&FundType=11';
    var r6 = await httpGet(url6);
    console.log(r6.slice(0, 800));
  } catch(e) { console.log('err:', e.message); }
}

testAPIs().catch(console.error);
