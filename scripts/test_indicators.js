/**
 * 快速测试东方财富指标接口（HTTPS版）
 */
const https = require('https');
const http = require('http');
const fs = require('fs');

function httpGet(url, timeoutMs = 6000) {
  const mod = url.startsWith('https') ? https : http;
  return new Promise((resolve, reject) => {
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.eastmoney.com' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
    });
    req.on('error', () => resolve(''));
    req.setTimeout(timeoutMs, () => { req.destroy(); resolve(''); });
  });
}

function ema(data, period) {
  const k = 2 / (period + 1);
  const result = [data[0]];
  for (let i = 1; i < data.length; i++) result.push(data[i] * k + result[i - 1] * (1 - k));
  return result;
}

async function testEM(code, market, label) {
  const mkt = market === 'SH' ? 1 : 0;
  const url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=' + mkt + '.' + code + '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=60';
  const raw = await httpGet(url);
  if (!raw) { console.log(label + ' ' + code + ': ❌ 无响应'); return null; }
  try {
    const json = JSON.parse(raw);
    if (!json.data || !json.data.klines || json.data.klines.length < 25) {
      console.log(label + ' ' + code + ' ❌ 数据不足(' + (json.data?.klines?.length || 0) + '条)');
      return null;
    }
    const klines = json.data.klines;
    const closes = klines.map(k => parseFloat(k.split(',')[2]));
    const ma20 = closes.slice(-20).reduce((s, v) => s + v, 0) / 20;
    const e12 = ema(closes, 12);
    const e26 = ema(closes, 26);
    const macdLine = closes.map((_, i) => e12[i] - e26[i]);
    const sig9 = ema(macdLine, 9);
    const macd = macdLine[macdLine.length - 1];
    const sig = sig9[sig9.length - 1];
    const hist = macd - sig;
    const aboveMA20 = closes[closes.length-1] > ma20;
    const aboveZero = macd > 0;
    const stars = (aboveMA20 && aboveZero) ? 2 : aboveMA20 ? 1 : 0;
    console.log(label + '(' + code + '): ✅ K=' + klines.length + ' 昨收=' + closes[closes.length-2].toFixed(3) + ' MA20=' + ma20.toFixed(3) + ' MACD=' + hist.toFixed(4) + ' ⭐' + stars + ' | ' + (aboveMA20?'站上MA20 ':'MA20下') + (aboveZero?'零轴上':'零轴下'));
    return { code, name: label, closes, ma20, macd: hist, stars };
  } catch(e) { console.log(label + ' ❌ 解析错误:', e.message); return null; }
}

async function main() {
  const tests = [
    ['159681', 'SZ', '创业板50ETF'],
    ['159329', 'SZ', '沙特ETF'],
    ['159100', 'SZ', '巴西'],
    ['512770', 'SH', '战略新兴'],
    ['513100', 'SH', '纳指ETF'],
    ['159985', 'SZ', '豆粕ETF'],
    ['512660', 'SH', '军工ETF'],
    ['515700', 'SH', '新能源车'],
    ['518880', 'SH', '黄金ETF'],
  ];
  for (const [code, mkt, name] of tests) {
    await testEM(code, mkt, name);
    await new Promise(r => setTimeout(r, 300));
  }
}
main();
