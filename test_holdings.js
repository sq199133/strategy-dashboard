const https = require('https');
const fs   = require('fs');
const path = require('path');

const ALL_ETFS = require('./data/etf_pool.js');

// ── HTTP ──────────────────────────────────────────
function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://gu.qq.com/'
      }
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(12000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

// ── 腾讯基金持仓接口 ──────────────────────────────
async function getTopHoldings(code, market) {
  // 腾讯财经基金持仓接口
  var secid = market === 'SH' ? 'sh' + code : 'sz' + code;
  // 腾讯基金详情接口（含重仓股）
  var url = 'https://web.ifzq.gtimg.cn/appfund/app/fundinfo?param=' + secid + ',,,3,,10,,1';
  try {
    var raw = await httpGet(url);
    var j = JSON.parse(raw);
    // 返回的持仓股票列表
    var stocks = j.data && j.data.zzgp && j.data.zzgp.zqList;
    if (!stocks || stocks.length === 0) return [];
    return stocks.slice(0, 10).map(s => ({
      code:   s.Param || '',
      name:   s.ProductName || s.Name || s.name || '',
      weight: parseFloat(s.Ratio || s.ratio || s.Weight || s.weight || 0)
    }));
  } catch(e) {
    return null; // 接口失败
  }
}

async function main() {
  // 先测5只看接口返回什么
  var tests = [
    {code:'510300', name:'沪深300ETF',    market:'SH'},
    {code:'510310', name:'沪深300ETF易方达',market:'SH'},
    {code:'159919', name:'沪深300ETF嘉实', market:'SZ'},
    {code:'513100', name:'纳指ETF',        market:'SH'},
    {code:'159981', name:'纳指ETF',        market:'SZ'},
  ];

  console.log('测试腾讯基金持仓接口...\n');
  for (var t of tests) {
    process.stdout.write(t.code + ' ' + t.name + ' ... ');
    var holdings = await getTopHoldings(t.code, t.market);
    if (holdings === null) {
      console.log('接口失败');
    } else if (holdings.length === 0) {
      console.log('无持仓数据');
    } else {
      console.log('获取到 ' + holdings.length + ' 只持仓');
      holdings.forEach(h => console.log('  ' + h.code + ' ' + h.name + ' ' + h.weight + '%'));
    }
    await new Promise(r => setTimeout(r, 500));
  }
}

main().catch(console.error);
