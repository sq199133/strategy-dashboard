// Build comprehensive ETF pool from East Money data
// Step 1: Fetch ALL ETFs (all pages)
// Step 2: Filter size >= 2亿, dedup by tracking index (keep largest)
// Step 3: Categorize and save
const https = require('https');
const fs = require('fs');
const path = require('path');

function fetchEMPage(page, pz) {
  const url = `https://push2.eastmoney.com/api/qt/clist/get?pn=${page}&pz=${pz}&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20,f100`;
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

// Get fund details including tracking index
function fetchFundDetail(code, market) {
  const secid = market === 'SZ' ? '0.' + code : '1.' + code;
  const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&fields=f57,f58,f84,f127,f128,f131`;
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

// Category mapping based on name keywords
function categorize(name) {
  // A股宽基
  if (/上证50|沪深300|中证500|中证1000|中证2000|中证800|创业板|科创50|科创100|科创200|深证100|深证成指|中证A50|中证A500|A500|A50/.test(name) && !/医药|军工|芯片|半导体|人工智能|新能源|机器人|通信|5G|有色|稀土|光伏|电池|储能|电网|卫星|航空|央企|创新|成长|低波|红利|质量|价值/.test(name)) {
    return 'A股宽基';
  }
  // 科技
  if (/芯片|半导体|人工智能|AI|通信|5G|TMT|信息技术|软件|计算机|大数据|云计算|数字|物联网|电信|科技/.test(name)) {
    return '科技';
  }
  // 高端制造
  if (/机器人|航天|军工|航空|制造|工业|高端/.test(name)) {
    return '高端制造';
  }
  // 新能源
  if (/新能源|光伏|电池|储能|电网|低碳|环保|碳中和|绿色/.test(name)) {
    return '新能源';
  }
  // 消费医药
  if (/消费|医药|生物|酒|食品|家电|养殖|农业|养老|医疗|保健|中药|餐饮|旅游|传媒|游戏|影视|体育|动漫|纺织|服装|汽车|新能源车/.test(name)) {
    return '消费医药';
  }
  // 金融地产
  if (/银行|证券|保险|地产|房地产|金融/.test(name)) {
    return '金融地产';
  }
  // 周期资源
  if (/有色|稀土|煤炭|钢铁|化工|石油|黄金|矿业|资源|金属|原油|天然气/.test(name)) {
    return '周期资源';
  }
  // 策略指数
  if (/红利|低波|价值|成长|质量|动量|Smart|增强|优选|央企|国企|创新/.test(name)) {
    return '策略指数';
  }
  // 港股/海外
  if (/恒生|港|中概|互联|纳斯达克|纳指|标普|道琼斯|日经|德国|法国|越南|印度|日本|英国|全球|海外|QD/.test(name)) {
    return '跨境QDII';
  }
  // 商品
  if (/豆粕|期货|商品|能源化工/.test(name)) {
    return '商品';
  }
  return '其他';
}

async function main() {
  console.log('=== 获取全市场ETF数据 ===\n');
  
  // Fetch all pages
  let allEtfs = [];
  for (let p = 1; p <= 6; p++) {
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
          size: d.f20 ? d.f20 / 1e8 : 0,
        });
      });
      console.log('Page ' + p + ': ' + r.data.diff.length + ' 只, 累计 ' + allEtfs.length);
    }
    await new Promise(r => setTimeout(r, 300));
  }
  
  console.log('\n总计: ' + allEtfs.length + ' 只ETF');
  
  // Filter size >= 2亿
  const filtered = allEtfs.filter(e => e.size >= 2);
  console.log('规模>=2亿: ' + filtered.length + ' 只');
  
  // Sort by size desc
  filtered.sort((a, b) => b.size - a.size);
  
  // Categorize
  filtered.forEach(e => { e.category = categorize(e.name); });
  
  // Dedup: for similar names (same index), keep the largest
  // Build a map of dedup key → best ETF
  const dedupMap = {};
  filtered.forEach(e => {
    // Create a simplified key for deduplication
    let key = e.name
      .replace(/ETF|指数|基金|联接/g, '')
      .replace(/\s+/g, '');
    if (!dedupMap[key] || e.size > dedupMap[key].size) {
      dedupMap[key] = e;
    }
  });
  
  const deduped = Object.values(dedupMap);
  deduped.sort((a, b) => b.size - a.size);
  console.log('去重后: ' + deduped.length + ' 只\n');
  
  // Show by category
  const categories = {};
  deduped.forEach(e => {
    if (!categories[e.category]) categories[e.category] = [];
    categories[e.category].push(e);
  });
  
  console.log('===== 分类统计 =====');
  Object.keys(categories).sort().forEach(cat => {
    console.log(cat + ': ' + categories[cat].length + ' 只');
  });
  
  // Build final pool: pick top N per category
  // A股宽基: 15, 科技: 12, 高端制造: 8, 新能源: 8, 消费医药: 10, 金融地产: 6, 周期资源: 6, 策略指数: 6, 跨境QDII: 10, 商品: 4, 其他: 5
  const limits = {
    'A股宽基': 15, '科技': 12, '高端制造': 8, '新能源': 8, 
    '消费医药': 10, '金融地产': 6, '周期资源': 6, '策略指数': 6, 
    '跨境QDII': 12, '商品': 4, '其他': 5
  };
  
  const finalPool = [];
  Object.keys(categories).sort().forEach(cat => {
    const limit = limits[cat] || 8;
    const items = categories[cat].slice(0, limit);
    items.forEach(e => {
      finalPool.push({
        code: e.code,
        name: e.name,
        category: e.category,
        index: '',  // to be filled
        market: e.market,
        size: parseFloat(e.size.toFixed(1))
      });
    });
  });
  
  // Sort by category then size
  finalPool.sort((a, b) => {
    const catOrder = ['A股宽基','科技','高端制造','新能源','消费医药','金融地产','周期资源','策略指数','跨境QDII','商品','其他'];
    const ca = catOrder.indexOf(a.category);
    const cb = catOrder.indexOf(b.category);
    if (ca !== cb) return ca - cb;
    return b.size - a.size;
  });
  
  console.log('\n===== 最终标的池 (' + finalPool.length + '只) =====\n');
  let lastCat = '';
  finalPool.forEach((e, i) => {
    if (e.category !== lastCat) {
      console.log('\n--- ' + e.category + ' ---');
      lastCat = e.category;
    }
    console.log('  ' + e.code + ' ' + e.name + ' (' + e.market + ') ' + e.size + '亿');
  });
  
  // Save
  fs.writeFileSync(path.join(__dirname, 'etf_pool_v2.json'), JSON.stringify(finalPool, null, 2));
  console.log('\n已保存到 etf_pool_v2.json');
  
  // Also check our current holdings
  console.log('\n===== 当前持仓代码验证 =====');
  const holdings = ['159681', '512770', '512220', '516390', '513100'];
  holdings.forEach(code => {
    const found = allEtfs.find(e => e.code === code);
    if (found) {
      console.log(code + ' = ' + found.name + ' (规模' + found.size.toFixed(1) + '亿)');
    }
  });
}
main();
