/**
 * 腾讯接口修复版
 * 深市基金: data.szXXXXXX.day
 * 沪市基金: data.shXXXXXX.qfqday
 * 每项: ["日期", 开, 收, 高, 低, 成交量, ...]
 */
const https = require('https');

function g(url) {
  return new Promise(r => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => r(d));
    }).on('error', () => r(''));
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
  const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayfqfund&param=' + sym + ',day,,,60,qfq';
  const d = await g(url);
  if (!d) { console.log(code + ': 无响应'); return; }

  try {
    // 去掉 var xxx= 前缀
    const jsonStr = d.replace(/^[^=]+=/, '');
    const json = JSON.parse(jsonStr);
    const fund = json.data && (json.data['sz' + code] || json.data['sh' + code]);
    if (!fund) { console.log(code + ': 无fund数据'); return; }

    // 优先qfqday，其次day
    const dayArr = fund.qfqday || fund.day;
    if (!dayArr || dayArr.length < 25) { console.log(code + ': K线不足(' + (dayArr?.length || 0) + ')'); return; }

    // 收盘价: index 2
    const closes = dayArr.map(k => parseFloat(k[2]));
    const ma20 = closes.slice(-20).reduce((s, v) => s + v, 0) / 20;
    const e12 = ema(closes, 12), e26 = ema(closes, 26);
    const macdLine = closes.map((_, i) => e12[i] - e26[i]);
    const sig9 = ema(macdLine, 9);
    const macdHist = macdLine[macdLine.length - 1] - sig9[sig9.length - 1];
    const aboveMA20 = closes[closes.length - 1] > ma20;
    const aboveZero = macdLine[macdLine.length - 1] > 0;
    const stars = (aboveMA20 && aboveZero) ? 2 : aboveMA20 ? 1 : 0;

    console.log(code + ' ✅ K=' + dayArr.length + ' 昨=' + closes[closes.length - 2].toFixed(3) + ' MA20=' + ma20.toFixed(3) + ' MACD=' + macdHist.toFixed(4) + ' ⭐' + stars + ' (' + (aboveMA20?'上MA20 ':'下MA20') + (aboveZero?'零轴上':'零轴下') + ')');
    return { code, closes };
  } catch(e) {
    console.log(code + ': ❌ ' + e.message);
    return null;
  }
}

async function main() {
  const tests = [
    ['159681', 'SZ'], ['510500', 'SH'], ['588000', 'SH'],
    ['512770', 'SH'], ['513100', 'SH'], ['159329', 'SZ'],
    ['159100', 'SZ'], ['159985', 'SZ'], ['512660', 'SH'],
  ];
  for (const [code, mkt] of tests) {
    await test(code, mkt);
    await new Promise(r => setTimeout(r, 400));
  }
}
main();
