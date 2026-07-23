// Multi-source ETF data fetcher
// Sources: Sina, Tencent, THS (同花顺), 163 (网易财经)
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

function fetch(url, timeout = 10000) {
  return new Promise((resolve) => {
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, { timeout, headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Referer': 'https://finance.sina.com.cn'
    }}, (res) => {
      let data = '';
      // Handle redirects
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return fetch(res.headers.location, timeout).then(resolve);
      }
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ ok: true, status: res.statusCode, data, headers: res.headers }));
    }).on('error', e => resolve({ ok: false, error: e.message }));
  });
}

async function main() {
  const results = {};
  
  // ===== Source 1: Sina ETF list =====
  console.log('=== Source 1: Sina Finance ETF List ===');
  try {
    const r = await fetch('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=2000&sort=symbol&asc=1&node=etf_hq_fund&_s_r_a=auto');
    if (r.ok && r.data) {
      // Try parse as JSON
      try {
        // Sina returns format: var data = [...];
        let jsonStr = r.data;
        if (jsonStr.includes('var ')) jsonStr = jsonStr.replace(/^[^[]*/, '');
        jsonStr = jsonStr.replace(/;?\s*$/, '');
        const list = JSON.parse(jsonStr);
        results.sina = list;
        console.log('Sina: got ' + list.length + ' ETFs');
        if (list.length > 0) {
          console.log('Sample:', JSON.stringify(list[0]).substring(0, 200));
        }
      } catch(e) {
        console.log('Sina parse error:', e.message);
        console.log('Raw first 300:', r.data.substring(0, 300));
      }
    }
  } catch(e) { console.log('Sina failed:', e.message); }
  
  await new Promise(r => setTimeout(r, 500));
  
  // ===== Source 2: Tencent Finance ETF list =====
  console.log('\n=== Source 2: Tencent Finance ===');
  try {
    const r = await fetch('https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rankBK/getBK?type=etf&sort=3&direction=0&start=0&num=2000&_var=kline_dayqfq');
    if (r.ok && r.data) {
      try {
        let jsonStr = r.data;
        if (jsonStr.includes('=')) jsonStr = jsonStr.replace(/^[^=]*=/, '').trim();
        jsonStr = jsonStr.replace(/;?\s*$/, '');
        const list = JSON.parse(jsonStr);
        results.tencent = list;
        console.log('Tencent: got data');
        console.log('Sample:', JSON.stringify(list).substring(0, 500));
      } catch(e) {
        console.log('Tencent parse error:', e.message);
        console.log('Raw first 300:', r.data.substring(0, 300));
      }
    }
  } catch(e) { console.log('Tencent failed:', e.message); }
  
  await new Promise(r => setTimeout(r, 500));
  
  // ===== Source 3: 163 (网易) ETF list =====
  console.log('\n=== Source 3: 163 Finance ===');
  try {
    const r = await fetch('https://quotes.money.163.com/hs/service/diyrank.php?host=http%3A%2F%2Fquotes.money.163.com%2Fhs%2Fservice%2Fdiyrank.php&page=0&query=STYPE%3AEQA&fields=NO%2CSYMBOL%2CNAME%2CPRICE%2CPERCENT%2CUPDOWN%2CFIVE_MINUTE%2COPEN%2CYESTCLOSE%2CHIGH%2CLOW%2CVOLUME%2CTURNOVER%2CHS%2CLB%2CWB%2CZF%2CPE%2CMCAP%2CTCAP%2CMFSUM%2CMFRATIO.MFRATIO2%2CMFRATIO.MFRATIO10%2CSNAME%2CCODE%2CANNOUNMT%2CUVSNEWS&sort=PERCENT&order=desc&count=2000&type=query');
    if (r.ok && r.data) {
      try {
        const j = JSON.parse(r.data);
        results.netease = j;
        console.log('163: got ' + (j.list ? j.list.length : 'no list') + ' items');
        if (j.list && j.list.length > 0) {
          console.log('Sample:', JSON.stringify(j.list[0]).substring(0, 200));
        }
      } catch(e) {
        console.log('163 parse error:', e.message);
        console.log('Raw first 300:', r.data.substring(0, 300));
      }
    }
  } catch(e) { console.log('163 failed:', e.message); }
  
  await new Promise(r => setTimeout(r, 500));
  
  // ===== Source 4: 同花顺 ETF list via iwencai =====
  console.log('\n=== Source 4: 同花顺 iwencai ===');
  try {
    const r = await fetch('https://www.iwencai.com/unifiedwap/result?w=全部ETF基金&querytype=stock&sort=asc&orderby=code&iss=pc&pagesize=2000&page=1');
    if (r.ok) {
      console.log('THS status:', r.status);
      console.log('THS data length:', r.data.length);
      console.log('THS first 500:', r.data.substring(0, 500));
    }
  } catch(e) { console.log('THS failed:', e.message); }
  
  await new Promise(r => setTimeout(r, 500));
  
  // ===== Source 5: 东方财富 specific QDII/跨境 ETF query =====
  console.log('\n=== Source 5: East Money QDII ETFs ===');
  try {
    const r = await fetch('https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=200&po=1&np=1&fltt=2&invt=2&fid=f20&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20');
    if (r.ok && r.data) {
      try {
        const j = JSON.parse(r.data);
        console.log('EM QDII: total=' + (j.data?.total || 0));
        if (j.data?.diff) {
          // filter for QDII-like names
          const qdii = j.data.diff.filter(d => 
            /恒生|港|中概|互联|纳斯达克|纳指|标普|道琼斯|日经|德国|法国|越南|印度|日本|英国|全球|海外|QD|MSCI|美国|美股|豆粕|黄金|白银|商品/.test(d.f14)
          );
          console.log('EM QDII matches: ' + qdii.length);
          qdii.slice(0, 20).forEach(d => console.log('  ' + d.f12 + ' ' + d.f14 + ' ' + (d.f20/1e8).toFixed(1) + '亿'));
        }
      } catch(e) { console.log('EM parse error:', e.message); }
    }
  } catch(e) { console.log('EM failed:', e.message); }
  
  // Save raw results
  fs.writeFileSync(path.join(__dirname, 'multi_source_raw.json'), JSON.stringify(results, null, 2));
  console.log('\nRaw results saved to multi_source_raw.json');
  
  // ===== Source 6: Try East Money with all pages for ETF type filter =====
  console.log('\n=== Source 6: East Money all ETFs page 1-6 ===');
  let emAll = [];
  for (let p = 1; p <= 6; p++) {
    try {
      const r = await fetch('https://push2.eastmoney.com/api/qt/clist/get?pn=' + p + '&pz=200&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20');
      if (r.ok && r.data) {
        const j = JSON.parse(r.data);
        if (j.data?.diff) {
          j.data.diff.forEach(d => emAll.push({
            code: d.f12, market: d.f13===0?'SZ':'SH', name: d.f14,
            price: d.f2, pct: d.f3, size: d.f20 ? d.f20/1e8 : 0
          }));
        }
      }
      await new Promise(r => setTimeout(r, 200));
    } catch(e) {}
  }
  console.log('EM all ETFs: ' + emAll.length);
  
  // Filter QDII/cross-border
  const qdiiAll = emAll.filter(e => 
    /恒生|港|中概|互联|纳斯达克|纳指|标普|道琼斯|日经|德国|法国|越南|印度|日本|英国|全球|海外|QD|MSCI|美国|美股/.test(e.name)
  );
  qdiiAll.sort((a,b) => b.size - a.size);
  console.log('\nAll QDII ETFs (from EM):');
  qdiiAll.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  // Filter commodities
  const commodityAll = emAll.filter(e => 
    /豆粕|黄金|白银|上海金|商品|期货|能源化工|有色期货/.test(e.name)
  );
  commodityAll.sort((a,b) => b.size - a.size);
  console.log('\nAll Commodity ETFs:');
  commodityAll.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  // Filter bio/medical
  const bioAll = emAll.filter(e => 
    /医药|生物|中药|医疗|保健|健康|疫苗/.test(e.name)
  );
  bioAll.sort((a,b) => b.size - a.size);
  console.log('\nAll Bio/Medical ETFs:');
  bioAll.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  // Filter EV
  const evAll = emAll.filter(e => 
    /新能源车|新能车|电动汽车|智能汽车/.test(e.name)
  );
  evAll.sort((a,b) => b.size - a.size);
  console.log('\nAll EV ETFs:');
  evAll.forEach(e => console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿'));
  
  // Save all
  fs.writeFileSync(path.join(__dirname, 'etf_all_pages.json'), JSON.stringify(emAll, null, 2));
  console.log('\nAll EM ETFs saved to etf_all_pages.json (' + emAll.length + ')');
}
main();
