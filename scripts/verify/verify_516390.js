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
async function main() {
  const tests = [
    ['SH', '516390', '516390（建仓持仓）'],
    ['SH', '515700', '515700（建议替换）'],
  ];
  for (const [mkt, code, label] of tests) {
    const sym = (mkt === 'SH' ? 'sh' : 'sz') + code;
    const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayfqfund&param=' + sym + ',day,,,60,qfq';
    const d = await g(url);
    if (!d) { console.log(label + ': 无响应'); continue; }
    try {
      const j = JSON.parse(d.replace(/^[^=]+=/, ''));
      const fund = j.data && (j.data['sh' + code] || j.data['sz' + code]);
      if (!fund) { console.log(label + ': 无数据'); continue; }
      const arr = fund.qfqday || fund.day;
      console.log(label + ': qfqday=' + (fund.qfqday ? '有' : '无') + ' day=' + (fund.day ? '有' : '无') + ' 共' + (arr?.length || 0) + '条');
      if (arr && arr.length > 0) {
        console.log('  最新:' + arr[arr.length - 1]?.[0] + ' 昨收=' + arr[arr.length - 1]?.[2] + ' 开盘=' + arr[arr.length - 1]?.[1]);
        console.log('  名称来自腾讯: ' + (fund.name || '无'));
      }
    } catch(e) { console.log(label + ': ' + e.message); }
    await new Promise(r => setTimeout(r, 500));
  }
}
main();
