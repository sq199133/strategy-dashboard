const { execSync } = require('child_process');
const fs = require('fs');
const pool = require('D:/QClaw_Trading/data/etf_pool.js');

// 判断交易所前缀
function prefix(code) {
  if (code.startsWith('5') || code.startsWith('51')) return 'sh';
  if (code.startsWith('1') && code.length === 6) return 'sh';
  return 'sz';
}

// 批量抓行情（每批50只）
async function fetchQuotes(codes) {
  const results = {};
  const batches = [];
  for (let i = 0; i < codes.length; i += 50) {
    batches.push(codes.slice(i, i + 50));
  }

  for (const batch of batches) {
    const q = batch.map(c => prefix(c) + c).join(',');
    let out = '';
    try {
      out = execSync(`curl.exe -s --max-time 15 "https://qt.gtimg.cn/q=${q}"`, { encoding: 'utf8', timeout: 20000 });
    } catch(e) {
      console.log('curl失败:', e.message);
      return results;
    }

    const lines = out.trim().split('\n');
    for (const line of lines) {
      // v_sh510300="1~name~code~price~close~open~vol~..."
      const m = line.match(/v_(sh|sz)(\d+)[^=]*="([^"]*)"/);
      if (!m) continue;
      const code = m[2];
      const f = m[3].split('~');
      // 字段说明（腾讯行情Ashare ETF格式）：
      // f[3]=当前价  f[4]=昨收  f[5]=今开  f[6]=成交量(手)
      // f[31]=涨跌额  f[32]=涨跌幅%  f[34]=NAV估算  f[36]=溢价率
      // f[39]=管理费  f[47]=52W高  f[48]=52W低  f[51]=年初至今%
      // 最后字段 = per_share_nav（如 796571.1080）
      const raw = line.split('~');
      const lastField = raw[raw.length - 1].replace(/"/g, '').trim();

      results[code] = {
        price: f[3] || '-',
        close: f[4] || '-',
        open: f[5] || '-',
        vol: f[6] || '-',
        change: f[31] || '-',
        pct: f[32] || '-',
        nav: f[34] || '-',       // NAV估算
        premium: f[36] || '-',
        fee: f[39] || '-',
        high52w: f[47] || '-',
        low52w: f[48] || '-',
        ytd: f[51] || '-',
        perShareNav: lastField || '-',
      };
    }
  }
  return results;
}

async function main() {
  const results = await fetchQuotes(pool.map(e => e.code));
  
  const now = new Date();
  const isTradingDay = now.getDay() >= 1 && now.getDay() <= 5;
  const hour = now.getHours();
  const isTradingHour = hour >= 9 && hour < 15;
  const timeNote = isTradingDay && isTradingHour ? '【交易时段】' : '【非交易时段，价格为昨收】';
  
  console.log(`\n=== ETF标的池 v5.1（共${pool.length}只） ${timeNote}===\n`);
  
  // 按类别分组
  const cats = {};
  pool.forEach(e => {
    const c = e.category || '-';
    if (!cats[c]) cats[c] = [];
    cats[c].push(e);
  });

  let idx = 0;
  for (const [cat, items] of Object.entries(cats)) {
    console.log(`\n【${cat}】(${items.length}只)`);
    console.log('  序号  代码      名称                  现价     昨收     涨跌      涨跌幅%   估算NAV  类别');
    console.log('  ' + '─'.repeat(105));
    
    for (const etf of items) {
      idx++;
      const r = results[etf.code] || {};
      const price = r.price || '-';
      const close = r.close || '-';
      const pct = r.pct || '-';
      const chg = r.change || '-';
      const nav = r.nav || '-';
      
      const pctStr = pct !== '-' ? (parseFloat(pct) > 0 ? '+' + pct + '%' : pct + '%') : '-';
      const navStr = nav !== '-' ? parseFloat(nav).toFixed(4) : '-';
      
      console.log(
        `  ${String(idx).padStart(2)}.  ${etf.code}  ${etf.name.padEnd(14)}  ` +
        `${String(price).padStart(7)}  ${String(close).padStart(7)}  ` +
        `${String(chg).padStart(7)}  ${pctStr.padStart(8)}   ${navStr.padStart(7)}  ${cat}`
      );
    }
  }

  // 保存
  const enriched = pool.map((etf, i) => ({
    ...etf,
    index: i + 1,
    price: results[etf.code]?.price || null,
    close: results[etf.code]?.close || null,
    change: results[etf.code]?.change || null,
    pct: results[etf.code]?.pct || null,
    nav: results[etf.code]?.nav || null,
    premium: results[etf.code]?.premium || null,
    ytd: results[etf.code]?.ytd || null,
    high52w: results[etf.code]?.high52w || null,
    low52w: results[etf.code]?.low52w || null,
  }));
  fs.writeFileSync('D:/QClaw_Trading/data/etf_pool_with_price.json', JSON.stringify(enriched, null, 2), 'utf8');
  console.log('\n\n已保存至 data/etf_pool_with_price.json');
}

main().catch(e => console.error(e));