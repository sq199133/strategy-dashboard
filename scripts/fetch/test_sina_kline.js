const http = require('http');
function httpGet(url) {
  return new Promise(resolve => {
    http.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'http://finance.sina.com.cn' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
    }).on('error', () => resolve('')).setTimeout(6000, function() { this.destroy(); resolve(''); });
  });
}
function ema(data, period) {
  const k = 2 / (period + 1);
  const r = [data[0]];
  for (let i = 1; i < data.length; i++) r.push(data[i] * k + r[i - 1] * (1 - k));
  return r;
}
async function test(code, market) {
  const sym = (market === 'SH' ? 'sh' : 'sz') + code;
  const url = 'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=' + sym + '&type=day&data_type=normal&datalen=60';
  const raw = await httpGet(url);
  if (!raw) { console.log(code, '❌ 无响应'); return; }
  try {
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr) || arr.length < 25) { console.log(code, '❌ 数据不足:'+arr.length); return; }
    const closes = arr.map(k => parseFloat(k.close));
    const ma20 = closes.slice(-20).reduce((s,v)=>s+v,0)/20;
    const e12 = ema(closes,12), e26 = ema(closes,26);
    const macdLine = closes.map((_,i)=>e12[i]-e26[i]);
    const sig9 = ema(macdLine,9);
    const hist = macdLine[macdLine.length-1] - sig9[sig9.length-1];
    const above = closes[closes.length-1] > ma20;
    const aboveZ = macdLine[macdLine.length-1] > 0;
    const stars = (above&&aboveZ)?2:above?1:0;
    console.log(code+' ✅ K='+arr.length+' 昨='+closes[closes.length-2].toFixed(3)+' MA20='+ma20.toFixed(3)+' MACD='+hist.toFixed(4)+' ⭐'+stars);
  } catch(e) { console.log(code, '❌ 解析错误:'+e.message); }
}
async function main() {
  const tests = [
    ['510500','SH'],['588000','SH'],['159681','SZ'],
    ['512770','SH'],['513100','SH'],['159329','SZ'],['159100','SZ']
  ];
  for (const [c,m] of tests) { await test(c,m); await new Promise(r=>setTimeout(r,600)); }
}
main();
