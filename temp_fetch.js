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
    {s:'sh000300',n:'CSI300'},{s:'sz399006',n:'GEM'},{s:'sh000001',n:'SSE'},
    {s:'sh513100',n:'NAS100'},{s:'sh513500',n:'SP500'},
    {s:'sz159259',n:'GROWTH'},{s:'sh515700',n:'NEV'},{s:'sz159350',n:'SZ50'},
    {s:'sh518880',n:'GOLD'},{s:'sh588200',n:'STARCHIP'}
  ];
  
  for (const c of codes) {
    try {
      const j = await fetch('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + c.s + ',day,,,25,qfq');
      const data = j.data[c.s];
      if (!data || !data.day || data.day.length < 5) {
        console.log(c.n + '|NODATA');
        continue;
      }
      const kl = data.day;
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
      
      // MACD calc
      const closes = kl.map(k => parseFloat(k[3]));
      let difV='-', deaV='-', histV='-', macdSt='-';
      if (closes.length >= 27) {
        const ema = (d, p) => { let k=2/(p+1), r=[d[0]]; for(let i=1;i<d.length;i++) r.push(d[i]*k+r[i-1]*(1-k)); return r; };
        const e12 = ema(closes, 12), e26 = ema(closes, 26);
        const dif = e12.map((v,i) => v - e26[i]);
        let dea = [dif[0]]; const kk = 2/10;
        for(let i=1; i<dif.length; i++) dea.push(dif[i]*kk + dea[i-1]*(1-kk));
        const hist = dif.map((v,i) => 2*(v-dea[i]));
        const ld=dif[dif.length-1], lde=dea[dea.length-1];
        const pd=dif[dif.length-2], pde=dea[dea.length-2];
        difV = ld.toFixed(4);
        deaV = lde.toFixed(4);
        histV = hist[hist.length-1].toFixed(4);
        const gc = pd<=pde && ld>lde;
        const zu = ld>0 && lde>0;
        macdSt = gc ? 'GOLDEN' : (zu ? 'ZUP' : 'ZBL');
      }
      
      console.log(c.n + '|' + date + '|' + close + '|' + p1 + '|' + p5 + '|' + p20 + '|' + ma20 + '|' + difV + '|' + deaV + '|' + histV + '|' + macdSt);
    } catch(e) {
      console.log(c.n + '|ERR:' + e.message);
    }
  }
  process.exit(0);
})();
