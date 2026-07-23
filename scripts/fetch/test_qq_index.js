// 测试腾讯接口能否获取指数K线
var https = require('https');
function fetch(url) {
  return new Promise(function(resolve) {
    console.log('请求:', url);
    var req = https.get(url, {headers:{'Referer':'https://gu.qq.com/'}}, function(r) {
      console.log('状态:', r.statusCode);
      var chunks = [];
      r.on('data', function(c){ chunks.push(c); });
      r.on('end', function() {
        var d = Buffer.concat(chunks).toString('utf8');
        console.log('长度:', d.length);
        console.log('内容:', d.slice(0, 300));
        resolve();
      });
    });
    req.on('error', function(e){ console.log('网络错误:', e.message); resolve(); });
    req.setTimeout(10000, function(){ console.log('超时'); req.destroy(); resolve(); });
  });
}
async function main() {
  await fetch('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,300,qfq');
  process.exit(0);
}
main();
