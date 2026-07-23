// Test Sina Finance historical data for S&P 500
var https = require('https');

// Found: int_sp500 = 标普500指数, real-time quote works
// Now test historical data URLs

// Sina provides historical data for US stocks via:
// https://finance.sina.com.cn/realstock/company/gb_SPX/hisdata.shtml
// or direct CSV download

var options = {
  hostname: 'finance.sina.com.cn',
  path: '/realstock/company/gb_sp500/hisdata.shtml',
  headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
};

https.get(options, function(r) {
  console.log('Status: ' + r.statusCode);
  console.log('Headers: ' + JSON.stringify(r.headers).substring(0, 200));
  var d = '';
  r.on('data', function(c) { d += c; });
  r.on('end', function() {
    // Look for CSV or data links in the HTML
    if (d.indexOf('csv') > -1) {
      var idx = d.indexOf('csv');
      console.log('Found csv at pos ' + idx);
      console.log('Context: ' + d.substring(Math.max(0, idx - 100), idx + 100));
    }
    console.log('Total length: ' + d.length);
  });
}).on('error', function(e) { console.log('ERR: ' + e.message); });
