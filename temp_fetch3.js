const h = require('https');
function fetch(url) {
  return new Promise((resolve, reject) => {
    h.get(url, r => {
      let d = '';
      r.setEncoding('utf8');
      r.on('data', c => d += c);
      r.on('end', () => {
        try { resolve(JSON.parse(d)); } catch(e) { reject(e.message); }
      });
    }).on('error', reject);
  });
}

(async () => {
  const codes = [
    {s:'sh513100',n:'NAS100',m:'sh'},{s:'sh513500',n:'SP500',m:'sh'},
    {s:'sh518880',n:'GOLD',m:'sh'}
  ];
  
  for (const c of codes) {
    try {
      const j = await fetch('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + c.s + ',day,,,30,qfq');
      const key = Object.keys(j.data)[0];
      const stockData = j.data[key];
      // Try qfqday first, then day
      const kl = stockData.qfqday || stockData.day;
      if (!kl || kl.length < 5) {
        console.log(c.n + '|NODATA');
        continue;
      }
      const last = kl[kl.length - 1];
      const close = parseFloat(last[3]);
      const date = last[0];
      const prev = kl[kl.length - 2];
      const p1 = ((close - parseFloat(prev[3])) / parseFloat(prev[3]) * 100).toFixed(2);
      const i5 = Math.max(0, kl.length - 5);
      const p5 = ((close - parseFloat(kl[i5][3])) / parseFloat(kl[i5][3]) * 100).toFixed(2);
      const p20 = ((close - parseFloat(kl[0][3])) / parseFloat(kl[0][3]) * 100).toFixed(2);
      const last20 = kl.slice(-20);
      let sm = 0; last20.forEach(k => sm += parseFloat(k[3]));
      const ma20 = (sm / 20).toFixed(3);
      
      console.log(c.n + '|' + date + '|' + close + '|' + p1 + '|' + p5 + '|' + p20 + '|' + ma20);
    } catch(e) {
      console.log(c.n + '|ERR:' + e.message);
    }
  }
  process.exit(0);
})();
