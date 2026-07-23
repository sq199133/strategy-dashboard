const h = require('https');
const s = 'sh513100';
h.get('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + s + ',day,,,5,qfq', r => {
  let d = '';
  r.setEncoding('utf8');
  r.on('data', c => d += c);
  r.on('end', () => {
    console.log(d.substring(0, 1000));
    process.exit(0);
  });
});
