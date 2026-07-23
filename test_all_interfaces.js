const https = require('https');

function httpGet(url, referer) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': referer || 'https://gu.qq.com/'
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

async function testInterfaces() {
  var code = '510300';

  console.log('--- 测试1: 腾讯 fundminipro ---');
  try {
    var r = await httpGet('https://web.ifzq.gtimg.cn/appfund/app/fundminipro?param=' + code + '&type=zzgp', 'https://gu.qq.com/');
    console.log('fundminipro:', r.slice(0, 400));
  } catch(e) { console.log('err:', e.message); }

  console.log('\n--- 测试2: 腾讯 fundbasic ---');
  try {
    var r2 = await httpGet('https://proxy.finance.qq.com/ifzqgtimg/fund/fundbasic?_var=v_fundbasic&code=' + code, 'https://gu.qq.com/');
    console.log('fundbasic:', r2.slice(0, 400));
  } catch(e) { console.log('err:', e.message); }

  console.log('\n--- 测试3: 东方财富基金档案HTML ---');
  try {
    var r3 = await httpGet('https://fundf10.eastmoney.com/000311.html', 'https://fundf10.eastmoney.com/');
    // 找跟踪指数关键词
    var match = r3.match(/跟踪指数[:：][^<]{2,40}/);
    console.log('跟踪指数:', match ? match[0] : '未找到');
    // 找持仓股票
    var stocks = r3.match(/[0-9]{6}[^0-9]{2,10}[^<]{2,15}(涨|跌|平)/g);
    console.log('持仓关键词:', stocks ? stocks.slice(0,3) : '未找到');
  } catch(e) { console.log('err:', e.message); }

  console.log('\n--- 测试4: 中证指数公司API ---');
  try {
    var r4 = await httpGet('https://www.csindex.com.cn/zh沪股/510300', 'https://www.csindex.com.cn/');
    var match4 = r4.match(/跟踪指数[:：][^<]{2,40}/);
    console.log('中证:', match4 ? match4[0] : r4.slice(0, 200));
  } catch(e) { console.log('err:', e.message); }

  console.log('\n--- 测试5: 雪球ETF详情 ---');
  try {
    var r5 = await httpGet('https://xueqiu.com/S/SH' + code, 'https://xueqiu.com/');
    console.log('雪球(前200字):', r5.slice(0, 200));
  } catch(e) { console.log('err:', e.message); }

  console.log('\n--- 测试6: 天天基金网持仓 ---');
  try {
    var r6 = await httpGet('https://fundgz.1234567.com.cn/js/' + code + '.js?rt=1', 'https://fundf10.eastmoney.com/');
    console.log('天天基金持仓(前300字):', r6.slice(0, 300));
  } catch(e) { console.log('err:', e.message); }

  console.log('\n--- 测试7: 东方财富ETF详情 ---');
  try {
    var r7 = await httpGet('https://finance.sina.com.cn/fund/quotes/' + code + '/bc.shtml', 'https://finance.sina.com.cn/');
    console.log('新浪(前200字):', r7.slice(0, 200));
  } catch(e) { console.log('err:', e.message); }
}

testInterfaces().catch(console.error);
