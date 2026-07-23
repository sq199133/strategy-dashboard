// Test Sina Finance codes for US indices
var https = require('https');
var codes = ['gb_sp500','gb_.spx','gb_SPX','gb_SPY','gb_$dji','gb_$ixic','gb_$spx','int_spx','int_sp500','gb_$spx500'];
var first = codes.join(',');
var options = {
  hostname: 'hq.sinajs.cn',
  path: '/list=' + first,
  headers: { 'Referer': 'https://finance.sina.com.cn/', 'User-Agent': 'Mozilla/5.0' }
};
https.get(options, function(r) {
  var d = '';
  r.on('data', function(c) { d += c; });
  r.on('end', function() {
    var lines = d.trim().split('\n');
    lines.forEach(function(l) {
      // Extract variable name and value
      var m = l.match(/var hq_str_(\w+)=/);
      var val = l.match(/="(.*)"/);
      if (m) {
        var name = m[1];
        var value = val ? val[1] : '(empty)';
        if (value.length > 60) value = value.substring(0, 60) + '...';
        console.log(name + ' => ' + value);
      } else {
        console.log('PARSE_ERR: ' + l.substring(0, 80));
      }
    });
  });
}).on('error', function(e) { console.log('ERR: ' + e.message); });
