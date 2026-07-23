const fs = require('fs');
const pool = require('D:/QClaw_Trading/data/etf_pool.js');

const codes = pool.map(e => e.code);

// 用curl批量查腾讯行情（分2批，每批46只）
async function fetchQuotes(codes) {
  const batches = [];
  for (let i = 0; i < codes.length; i += 46) {
    batches.push(codes.slice(i, i + 46));
  }
  
  const results = {};
  
  for (const batch of batches) {
    const params = batch.map(c => `"${c}"`).join(',');
    const url = `https://qt.gtimg.cn/q=${params}`;
    const { execSync } = require('child_process');
    const out = execSync(`curl -s --max-time 15 "${url}"`, { encoding: 'utf8', timeout: 20000 });
    const lines = out.trim().split('\n');
    for (const line of lines) {
      const m = line.match(/v_(\d+)[^=]*="([^"]*)"/);
      if (m) {
        const code = m[1];
        const fields = m[2].split('~');
        if (fields.length > 3) {
          results[code] = {
            price: fields[3] || '-',    // 当前价
            nav: fields[4] || '-',       // 昨收/净值
            change: fields[31] || '-',  // 涨跌额
            pct: fields[32] || '-',     // 涨跌幅%
          };
        }
      }
    }
  }
  return results;
}

fetchQuotes(codes).then(results => {
  console.log(`\n=== ETF标的池 v5.1（共${pool.length}只）===\n`);
  console.log('序号  代码      名称                    现价    昨收/净值  涨跌     涨跌幅%  类别');
  console.log('─'.repeat(110));
  
  pool.forEach((etf, i) => {
    const code = etf.code;
    const r = results[code] || {};
    const price = r.price || '-';
    const nav = r.nav || '-';
    const pct = r.pct || '-';
    const chg = r.change || '-';
    const pctStr = pct !== '-' ? (parseFloat(pct) > 0 ? '+' + pct + '%' : pct + '%') : '-';
    console.log(
      `${String(i+1).padStart(2,'0')}.  ${code}  ${etf.name.padEnd(14,' ')}  ${String(price).padStart(7)}  ${String(nav).padStart(8)}  ${String(chg).padStart(7)}  ${pctStr.padStart(8)}  [${etf.category || '-'}]`
    );
  });
  
  // 保存结果
  const enriched = pool.map((etf, i) => ({
    ...etf,
    index: i + 1,
    price: results[etf.code]?.price || null,
    nav: results[etf.code]?.nav || null,
    change: results[etf.code]?.change || null,
    pct: results[etf.code]?.pct || null,
  }));
  
  fs.writeFileSync('D:/QClaw_Trading/data/etf_pool_with_price.json', JSON.stringify(enriched, null, 2), 'utf8');
  console.log('\n已保存至 data/etf_pool_with_price.json');
}).catch(e => {
  console.error('抓取失败:', e.message);
});