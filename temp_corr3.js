const https = require('https');
const http = require('http');

function httpGet(url) {
  const mod = url.startsWith('https') ? https : http;
  return new Promise(resolve => {
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
    });
    req.on('error', () => resolve(''));
    req.setTimeout(8000, () => { req.destroy(); resolve(''); });
  });
}

function fetchHistory(code, market, days) {
  const mkt = market === 'SH' ? 1 : 0;
  const url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=' + mkt + '.' + code + '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=' + days;
  return httpGet(url).then(d => {
    try {
      const json = JSON.parse(d);
      if (json.data && json.data.klines) {
        return json.data.klines.map(k => parseFloat(k.split(',')[2]));
      }
    } catch(e) {}
    return [];
  });
}

function calcReturns(closes) {
  const rets = [];
  for (let i = 1; i < closes.length; i++) {
    if (closes[i-1] > 0) rets.push((closes[i] - closes[i-1]) / closes[i-1]);
  }
  return rets;
}

function pearson(x, y) {
  const n = Math.min(x.length, y.length);
  if (n < 10) return 0;
  let sx=0,sy=0,sxy=0,sx2=0,sy2=0;
  for (let i=0;i<n;i++) { sx+=x[i];sy+=y[i];sxy+=x[i]*y[i];sx2+=x[i]*x[i];sy2+=y[i]*y[i]; }
  const num=n*sxy-sx*sy;
  const den=Math.sqrt((n*sx2-sx*sx)*(n*sy2-sy*sy));
  return den===0?0:num/den;
}

(async () => {
  const etfs = [
    { code: '159259', name: '成长ETF', market: 'SZ' },
    { code: '515700', name: '新能源车', market: 'SH' },
    { code: '159350', name: '深证50', market: 'SZ' },
    { code: '518880', name: '黄金ETF', market: 'SH' },
    { code: '513100', name: '纳指ETF', market: 'SH' }
  ];
  
  console.log('Fetching 120-day history...');
  const allRets = [];
  for (const e of etfs) {
    const closes = await fetchHistory(e.code, e.market, 130);
    const rets = calcReturns(closes);
    allRets.push(rets);
    console.log('  ' + e.code + ' ' + e.name + ': ' + rets.length + ' days');
    await new Promise(r => setTimeout(r, 150));
  }
  
  console.log('\n  ═══ Correlation Matrix (120-day daily returns, Pearson) ═══');
  const n = etfs.length;
  const header = '              ' + etfs.map(e => e.name.padEnd(9)).join('');
  console.log(header);
  
  const matrix = [];
  for (let i=0; i<n; i++) {
    matrix[i] = [];
    for (let j=0; j<n; j++) {
      if (i===j) matrix[i][j] = 1.0;
      else if (j<i) matrix[i][j] = matrix[j][i];
      else matrix[i][j] = pearson(allRets[i], allRets[j]);
    }
  }
  
  for (let i=0; i<n; i++) {
    let row = (etfs[i].name.padEnd(11));
    for (let j=0; j<n; j++) {
      const v = matrix[i][j];
      const color = v > 0.80 ? 'R' : v > 0.70 ? 'r' : v > 0.50 ? 'Y' : v > 0.30 ? 'y' : 'G';
      row += color + v.toFixed(3).padEnd(8);
    }
    console.log(row);
  }
  console.log('  R=Red(>0.80) r=red(>0.70) Y=Yellow(>0.50) y=yellow(>0.30) G=Green(<0.30)');
  
  // maxCorr for each
  console.log('\n  maxCorr per ETF:');
  for (let i=0; i<n; i++) {
    let maxC = 0;
    for (let j=0; j<n; j++) {
      if (i!==j && matrix[i][j]>maxC) maxC = matrix[i][j];
    }
    const ok = maxC <= 0.70 ? 'OK' : 'OVER';
    console.log('  ' + etfs[i].name + ': maxCorr=' + maxC.toFixed(3) + ' [' + ok + ']');
  }
  
  process.exit(0);
})();
