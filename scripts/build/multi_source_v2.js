// Multi-source ETF fetcher v2 - focus on what works
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

function httpGet(url, timeout = 12000) {
  return new Promise((resolve) => {
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, { timeout, headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }}, (res) => {
      let data = '';
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return httpGet(res.headers.location, timeout).then(resolve);
      }
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ ok: res.statusCode < 400, status: res.statusCode, data }));
    }).on('error', e => resolve({ ok: false, error: e.message }));
  });
}

async function main() {
  // ========== Sina ETF pages ==========
  console.log('=== 新浪 ETF (分页) ===');
  const allSina = [];
  for (let p = 1; p <= 10; p++) {
    const r = await httpGet('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=' + p + '&num=100&sort=symbol&asc=1&node=etf_hq_fund&_s_r_a=page' + p);
    if (r.ok && r.data) {
      try {
        let s = r.data.replace(/^[^[]*/, '').replace(/;?\s*$/, '');
        const list = JSON.parse(s);
        if (list.length === 0) { console.log('Page ' + p + ': empty, stopping'); break; }
        list.forEach(d => {
          // symbol like "sh510010"
          const sym = d.symbol || '';
          const code = sym.replace(/^(sh|sz)/, '').toUpperCase();
          const market = sym.startsWith('sh') ? 'SH' : 'SZ';
          allSina.push({
            code, market, name: d.name,
            price: parseFloat(d.trade) || 0,
            size: d.asset ? d.asset / 1e8 : (d.mktcap ? d.mktcap / 1e8 : 0),
            raw: d
          });
        });
        console.log('Page ' + p + ': +' + list.length + ', total ' + allSina.length);
      } catch(e) { console.log('Page ' + p + ' error: ' + e.message); break; }
    } else {
      console.log('Page ' + p + ': fetch failed');
      break;
    }
    await new Promise(r => setTimeout(r, 300));
  }
  console.log('Sina total: ' + allSina.length);
  
  // Show QDII from Sina
  const sinaQDII = allSina.filter(e => /恒生|港|中概|互联|纳斯达克|纳指|标普|道琼斯|日经|德国|法国|越南|印度|日本|英国|全球|海外|QD|MSCI|美国|美股/.test(e.name));
  sinaQDII.sort((a,b) => b.size - a.size);
  console.log('\nSina QDII ETFs (' + sinaQDII.length + '):');
  sinaQDII.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  const sinaCommodity = allSina.filter(e => /豆粕|黄金|白银|上海金|商品|期货|能源化工/.test(e.name));
  console.log('\nSina Commodity ETFs (' + sinaCommodity.length + '):');
  sinaCommodity.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  const sinaBio = allSina.filter(e => /医药|生物|中药|医疗|保健|健康/.test(e.name));
  console.log('\nSina Bio/Medical ETFs (' + sinaBio.length + '):');
  sinaBio.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  // ========== 天天基金 ETF list ==========
  console.log('\n=== 天天基金 ETF ===');
  const ttf = await httpGet('http://fund.eastmoney.com/JS/FundGuide/api/GetFundGuidePage.ashx?dt=0&ft=gp&sd=&ed=&sc=dmz&st=desc&pi=1&pn=200&zf=diy&sh=list');
  if (ttf.ok) {
    console.log('天天基金 status:', ttf.status, 'len:', ttf.data.length);
    console.log('First 500:', ttf.data.substring(0, 500));
  }
  
  await new Promise(r => setTimeout(r, 300));
  
  // ========== East Money alternative endpoints ==========
  console.log('\n=== 东方财富 alternatives ===');
  
  // Try the fundsearch API
  const em1 = await httpGet('https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchPageByField.ashx?m=1&key=ETF&pageindex=0&pagesize=100&field=trz&order=1&Datatype=JSON');
  if (em1.ok) {
    try {
      const j = JSON.parse(em1.data.replace(/^[^(]*\(/, '').replace(/\);?$/, ''));
      console.log('EM FundSearch: ' + (j.datas || []).length + ' funds');
    } catch(e) { console.log('EM FundSearch parse error'); console.log(em1.data.substring(0,300)); }
  }
  
  await new Promise(r => setTimeout(r, 300));
  
  // Try EM fund rank API
  const em2 = await httpGet('https://api.fund.eastmoney.com/FundRank/GetFundRankList?fundType=ETF&sort=dwjz&sortType=desc&pageIndex=1&pageSize=200&_=1', {
    timeout: 8000,
    headers: {
      'User-Agent': 'Mozilla/5.0',
      'Referer': 'https://fund.eastmoney.com/data/fundranking.html'
    }
  });
  if (em2.ok) {
    console.log('EM FundRank status:', em2.status, 'len:', em2.data.length);
    console.log('First 500:', em2.data.substring(0, 500));
  }
  
  await new Promise(r => setTimeout(r, 300));
  
  // ========== 腾讯自选股 API ==========
  console.log('\n=== 腾讯自选股 ===');
  const qq1 = await httpGet('https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rankBK/rank?type=etf&sort=3&direction=0&start=0&num=100&_var=kline');
  if (qq1.ok) {
    console.log('QQ status:', qq1.status, 'len:', qq1.data.length);
    console.log('First 300:', qq1.data.substring(0, 300));
  }
  
  // Save Sina data
  fs.writeFileSync(path.join(__dirname, 'sina_etf.json'), JSON.stringify(allSina, null, 2));
  console.log('\nSina data saved (' + allSina.length + ' ETFs)');
}
main();
