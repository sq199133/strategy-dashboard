// Fetch ALL Sina ETFs and save, then merge with EM data
const http = require('http');
const fs = require('fs');
const path = require('path');

function httpGet(url, timeout = 10000) {
  return new Promise((resolve) => {
    http.get(url, { timeout, headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }}, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', e => resolve(null));
  });
}

async function main() {
  // Step 1: Fetch Sina ETFs
  console.log('Fetching Sina ETFs...');
  const allSina = [];
  for (let p = 1; p <= 12; p++) {
    const data = await httpGet('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=' + p + '&num=100&sort=symbol&asc=1&node=etf_hq_fund&_s_r_a=page' + p);
    if (!data) break;
    try {
      let s = data.replace(/^[^[]*/, '').replace(/;?\s*$/, '');
      const list = JSON.parse(s);
      if (list.length === 0) break;
      list.forEach(d => {
        const sym = d.symbol || '';
        const code = sym.replace(/^(sh|sz)/, '').toUpperCase();
        const market = sym.startsWith('sh') ? 'SH' : 'SZ';
        allSina.push({ code, market, name: d.name, price: parseFloat(d.trade) || 0 });
      });
      console.log('  Page ' + p + ': +' + list.length + ', total ' + allSina.length);
    } catch(e) { break; }
    await new Promise(r => setTimeout(r, 200));
  }
  fs.writeFileSync(path.join(__dirname, 'sina_etf.json'), JSON.stringify(allSina, null, 2));
  console.log('Sina saved: ' + allSina.length + ' ETFs\n');
  
  // Step 2: Load EM size data
  let emSizeMap = {};
  try {
    const em = JSON.parse(fs.readFileSync(path.join(__dirname, 'etf_all_raw.json'), 'utf8'));
    em.forEach(e => { emSizeMap[e.code] = e.size; });
    console.log('EM size map loaded: ' + Object.keys(emSizeMap).length + ' entries\n');
  } catch(e) { console.log('No EM size data\n'); }
  
  // Step 3: Enrich & categorize
  allSina.forEach(e => { e.size = emSizeMap[e.code] || 0; });
  
  function categorize(name) {
    if (/中证A50|中证A500|A500ETF/.test(name)) return 'A股宽基';
    if (/上证50|沪深300|中证500|中证1000|中证2000|中证800/.test(name) && !/医药|军工|芯片|半导体|人工智能|新能源|机器人|有色|稀土|光伏|电池|储能|电网|卫星|航空|央企|低波|红利|质量|价值/.test(name)) return 'A股宽基';
    if (/创业板|科创50|科创100|科创200|深证100|深证成指|双创|科创创业/.test(name) && !/医药|军工|芯片|半导体|人工智能|新能源|机器人|有色|稀土|光伏|电池|储能|电网|卫星|航空|央企|低波|红利|质量|价值/.test(name)) return 'A股宽基';
    if (/芯片|半导体|人工智能|AI|通信|5G|TMT|信息技术|软件|计算机|大数据|云计算|数字|物联网|电信/.test(name)) return '科技';
    if (/机器人|航天|军工|航空|卫星/.test(name) && !/科技|互联|互联/.test(name)) return '高端制造';
    if (/新能源|光伏|电池|储能|电网|低碳|环保|碳中和|绿色|新能车|新能源车/.test(name)) return '新能源';
    if (/消费|医药|生物|酒|食品|家电|养殖|农业|养老|医疗|保健|中药|餐饮|旅游|传媒|游戏|影视|体育|动漫|汽车/.test(name) && !/科技|互联/.test(name)) return '消费医药';
    if (/银行|证券|保险|地产|房地产|金融/.test(name) && !/科技/.test(name)) return '金融地产';
    if (/有色|稀土|煤炭|钢铁|化工|石油|矿业|资源|金属|原油|天然气/.test(name)) return '周期资源';
    if (/红利|低波|价值|成长|质量|动量|增强|优选|央企|国企/.test(name) && !/港股|恒生|互联/.test(name)) return '策略指数';
    if (/恒生|港股|中概|互联|纳斯达克|纳指|标普|道琼斯|日经|德国|法国|越南|印度|日本|英国|全球|海外|QD|MSCI|美国|美股/.test(name)) return '跨境QDII';
    if (/豆粕|期货|商品|能源化工|黄金|白银|上海金/.test(name)) return '商品';
    return '其他';
  }
  
  allSina.forEach(e => { e.category = categorize(e.name); });
  
  // Dedup
  const dedupMap = {};
  allSina.forEach(e => {
    let key = e.name.replace(/ETF/g, '').replace(/\s+/g, '');
    if (!dedupMap[key] || (e.size > 0 && e.size > dedupMap[key].size)) dedupMap[key] = e;
    else if (e.size === 0 && dedupMap[key].size === 0 && e.code < dedupMap[key].code) dedupMap[key] = e;
  });
  
  const deduped = Object.values(dedupMap);
  deduped.forEach(e => { e.category = categorize(e.name); });
  
  // Group by category
  const categories = {};
  deduped.forEach(e => {
    if (!categories[e.category]) categories[e.category] = [];
    categories[e.category].push(e);
  });
  
  // Sort each category: known size first (desc), then unknown size by code
  Object.keys(categories).forEach(cat => {
    categories[cat].sort((a, b) => {
      if (a.size > 0 && b.size === 0) return -1;
      if (b.size > 0 && a.size === 0) return 1;
      if (a.size > 0 && b.size > 0) return b.size - a.size;
      return a.code.localeCompare(b.code);
    });
  });
  
  const catOrder = ['A股宽基','科技','高端制造','新能源','消费医药','金融地产','周期资源','策略指数','跨境QDII','商品','其他'];
  console.log('===== 分类统计 =====');
  catOrder.forEach(cat => {
    const items = categories[cat] || [];
    console.log(cat + ': ' + items.length + ' 只');
  });
  
  // Select pool
  const limits = {
    'A股宽基': 15, '科技': 10, '高端制造': 8, '新能源': 8,
    '消费医药': 10, '金融地产': 6, '周期资源': 6, '策略指数': 6,
    '跨境QDII': 15, '商品': 6, '其他': 5
  };
  
  const finalPool = [];
  catOrder.forEach(cat => {
    const items = (categories[cat] || []).slice(0, limits[cat] || 5);
    items.forEach(e => {
      finalPool.push({
        code: e.code, name: e.name, category: e.category,
        market: e.market, size: parseFloat(e.size.toFixed(1)) || 0
      });
    });
  });
  
  console.log('\n===== 最终标的池 v3 (' + finalPool.length + '只) =====\n');
  let lastCat = '';
  finalPool.forEach((e, i) => {
    if (e.category !== lastCat) {
      const total = (categories[e.category] || []).length;
      console.log('\n--- ' + e.category + ' (' + total + '只候选, 选前' + (limits[e.category]||5) + '只) ---');
      lastCat = e.category;
    }
    const s = e.size > 0 ? e.size + '亿' : '?亿';
    console.log('  ' + (i+1) + '. ' + e.code + ' ' + e.name + ' ' + s);
  });
  
  fs.writeFileSync(path.join(__dirname, 'etf_pool_v3.json'), JSON.stringify(finalPool, null, 2));
  console.log('\n已保存到 etf_pool_v3.json');
  
  // Holdings verification
  console.log('\n\n===== 持仓代码验证 =====');
  const holdings = [
    {code:'159681', intended:'创业板50ETF'},
    {code:'512770', intended:'生物医药ETF'},
    {code:'512220', intended:'军工ETF'},
    {code:'516390', intended:'新能源汽车ETF'},
    {code:'513100', intended:'纳指100ETF'},
  ];
  holdings.forEach(h => {
    const found = allSina.find(e => e.code === h.code);
    if (found) {
      const ok = found.name.includes(h.intended.substring(0,4)) || h.intended.includes(found.name.substring(0,4));
      console.log(h.code + ' | 期望=' + h.intended + ' | 实际=' + found.name + ' ' + (ok ? '✅' : '❌'));
    } else {
      console.log(h.code + ' | 期望=' + h.intended + ' | ❌ 不在列表');
    }
  });
  
  // Show full QDII list
  console.log('\n===== 跨境QDII 全部候选 =====');
  (categories['跨境QDII'] || []).forEach((e, i) => {
    const s = e.size > 0 ? e.size + '亿' : '?亿';
    console.log('  ' + (i+1) + '. ' + e.code + ' ' + e.name + ' ' + s);
  });
  
  // Show full 商品 list
  console.log('\n===== 商品 全部候选 =====');
  (categories['商品'] || []).forEach((e, i) => {
    const s = e.size > 0 ? e.size + '亿' : '?亿';
    console.log('  ' + (i+1) + '. ' + e.code + ' ' + e.name + ' ' + s);
  });
}
main();
