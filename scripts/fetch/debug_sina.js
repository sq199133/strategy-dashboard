const http = require('http');
function httpGet(url) {
  return new Promise(resolve => {
    http.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'http://finance.sina.com.cn' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => { console.log('Status:', res.statusCode); console.log('Raw:', d.substring(0, 500)); });
    }).on('error', e => console.log('err:', e.message));
  });
}
// 试不同格式
const tests = [
  'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh510500&type=day&data_type=normal&datalen=60',
  'http://finance.sina.com.cn/realstock/company/sh510500/nc.shtml',
  'http://hq.sinajs.cn/list=sh510500',
];
tests.forEach(url => { console.log('\n=== ' + url.substring(0,80) + ' ==='); httpGet(url); });
