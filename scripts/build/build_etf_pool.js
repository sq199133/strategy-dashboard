// Fetch ALL ETFs from East Money, filter by size >= 1亿, and organize
const https = require('https');
const fs = require('fs');
const path = require('path');

function fetchEMPage(page, pz) {
  const url = `https://push2.eastmoney.com/api/qt/clist/get?pn=${page}&pz=${pz}&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20,f115,f100`;
  return new Promise((resolve) => {
    https.get(url, { timeout: 15000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch(e) { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

// Search for specific ETFs by keyword
function searchETF(keyword) {
  const url = `https://searchapi.eastmoney.com/api/suggest/get?input=${encodeURIComponent(keyword)}&type=8&token=D43BF722C8E33BDC906FB84D85E326E8&count=10`;
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
  // 1. Get total count first
  const first = await fetchEMPage(1, 1);
  const total = first && first.data ? first.data.total : 0;
  console.log('全市场ETF总数: ' + total);
  
  // 2. Fetch all ETFs (in pages of 200)
  let allEtfs = [];
  const pages = Math.ceil(total / 200);
  for (let p = 1; p <= pages; p++) {
    const r = await fetchEMPage(p, 200);
    if (r && r.data && r.data.diff) {
      r.data.diff.forEach(d => {
        allEtfs.push({
          code: d.f12,
          market: d.f13 === 0 ? 'SZ' : 'SH',
          name: d.f14,
          price: d.f2,
          pct: d.f3,
          volume: d.f6,
          size: d.f20 ? d.f20 / 1e8 : 0,  // 亿元
          pe: d.f115
        });
      });
    }
    await new Promise(r => setTimeout(r, 300));
  }
  console.log('获取到 ' + allEtfs.length + ' 只ETF数据');
  
  // 3. Filter: size >= 1亿
  const filtered = allEtfs.filter(e => e.size >= 1);
  console.log('规模>=1亿: ' + filtered.length + ' 只');
  
  // 4. Sort by size descending
  filtered.sort((a, b) => b.size - a.size);
  
  // 5. Save full list
  fs.writeFileSync(path.join(__dirname, 'etf_all_raw.json'), JSON.stringify(filtered, null, 2));
  console.log('已保存到 etf_all_raw.json');
  
  // 6. Show top 80 by size
  console.log('\n===== 规模TOP 80 ETF =====');
  filtered.slice(0, 80).forEach((e, i) => {
    console.log((i+1) + '. ' + e.code + ' ' + e.name + ' 规模:' + e.size.toFixed(1) + '亿 价格:' + e.price);
  });
  
  // 7. Search for specific funds we need correct codes for
  console.log('\n===== 搜索关键ETF正确代码 =====');
  const keywords = ['生物医药', '军工', '人工智能', '煤炭', '科技龙头', '日经225', '富时A50', '白银', '中证1000', '保险', '稀有金属', '红利', '新能源车'];
  for (const kw of keywords) {
    const r = await searchETF(kw);
    if (r && r.QuotationCodeTable && r.QuotationCodeTable.Data) {
      const results = r.QuotationCodeTable.Data.filter(d => d.SecurityTypeName && d.SecurityTypeName.includes('ETF'));
      if (results.length > 0) {
        const top3 = results.slice(0, 3).map(d => d.Code + ' ' + d.Name).join(' | ');
        console.log(kw + ' → ' + top3);
      } else {
        console.log(kw + ' → 未找到ETF');
      }
    } else {
      console.log(kw + ' → 搜索失败');
    }
    await new Promise(r => setTimeout(r, 200));
  }
}
main();
