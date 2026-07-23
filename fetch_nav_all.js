/**
 * fetch_nav_all.js - 获取全部91只ETF的实时行情
 */
const { execSync } = require('child_process');
const fs = require('fs');

const pool = require('./data/etf_pool.js');
console.log('ETF总数:', pool.length);

// 分批构建股票代码列表 (每批40个)
function buildCodes(etfs) {
  return etfs.map(e => {
    const mkt = e.market === 'SZ' ? 'sz' : 'sh';
    return mkt + e.code;
  }).join(',');
}

function fetchBatch(codes) {
  const url = `https://qt.gtimg.cn/q=${codes}`;
  const cmd = `curl -s --connect-timeout 10 "${url}"`;
  try {
    const out = execSync(cmd, { encoding: 'gbk', timeout: 20000 });
    return out;
  } catch(e) {
    return '';
  }
}

const results = [];
const BATCH = 40;

for (let i = 0; i < pool.length; i += BATCH) {
  const batch = pool.slice(i, i + BATCH);
  const codes = buildCodes(batch);
  const raw = fetchBatch(codes);
  
  batch.forEach((etf, idx) => {
    const mkt = etf.market === 'SZ' ? 'sz' : 'sh';
    const key = `v_${mkt}${etf.code}`;
    const lines = raw.split('\n');
    let quote = null;
    for (const line of lines) {
      if (line.includes(key)) {
        // v_sz159338="1~中证A500ETF国泰~1.246~1.249~1.242~1.238~20250508~15:10:12~~1.246~11800~...
        const parts = line.split('~');
        if (parts.length > 10) {
          quote = {
            code: etf.code,
            name: etf.name,
            market: etf.market,
            category: etf.category,
            index: etf.index,
            price: parseFloat(parts[3]) || 0,    // 当前价
            nav: parseFloat(parts[4]) || 0,      // 昨净值/NAV
            change: parseFloat(parts[32]) || 0,  // 涨跌%
            date: parts[30] || '',
            time: parts[31] || ''
          };
        }
        break;
      }
    }
    if (!quote) {
      quote = {
        code: etf.code, name: etf.name, market: etf.market,
        category: etf.category, index: etf.index,
        price: 0, nav: 0, change: 0, date: '', time: '', error: true
      };
    }
    results.push(quote);
  });
  
  console.log(`批次 ${i/BATCH+1}/${Math.ceil(pool.length/BATCH)} 完成 (${results.length} 只)`);
  // no sleep needed
}

// 按分类排序
const byCat = {};
results.forEach(r => {
  if (!byCat[r.category]) byCat[r.category] = [];
  byCat[r.category].push(r);
});

console.log('\n\n' + '='.repeat(80));
console.log('ETF标的池 v5.1 实时行情检查');
console.log('='.repeat(80));

let totalErr = results.filter(r => r.error).length;
let noNav = results.filter(r => r.nav === 0).length;
console.log(`\n获取完成: ${results.length} 只  错误/无数据: ${totalErr} 只  无净值: ${noNav} 只\n`);

Object.keys(byCat).forEach(cat => {
  const etfs = byCat[cat];
  console.log(`\n【${cat}】(${etfs.length}只)`);
  console.log('代码       名称                  现价     净值     涨跌%');
  console.log('-'.repeat(65));
  etfs.forEach(e => {
    const flag = e.error ? '[!]' : e.nav === 0 ? '[?]' : '';
    const price = e.price > 0 ? e.price.toFixed(4) : 'N/A';
    const nav = e.nav > 0 ? e.nav.toFixed(4) : 'N/A';
    const chg = e.change !== 0 ? (e.change > 0 ? '+' : '') + e.change.toFixed(2) + '%' : 'N/A';
    console.log(`${flag}${e.code.padEnd(8)}${e.name.padEnd(16)}${price.padEnd(8)}${nav.padEnd(8)}${chg}`);
  });
});

fs.writeFileSync('./data/etf_pool_nav_check.json', JSON.stringify(results, null, 2));
console.log('\n已保存到 data/etf_pool_nav_check.json');