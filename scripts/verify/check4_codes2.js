const http = require('http');
function fetch(url) {
  return new Promise(resolve => {
    http.get(url, {headers:{'User-Agent':'Mozilla/5.0'}}, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end',()=>resolve(d));
    }).on('error',()=>resolve(''));
  });
}
async function main() {
  const codes = ['159329','159100','159980','159985'];
  for (const code of codes) {
    // EM fundgz API (real-time price)
    const r1 = await fetch('http://fundgz.1234567.com.cn/js/'+code+'.js?rt=1');
    console.log('EM fundgz ' + code + ':', r1);
    await new Promise(r=>setTimeout(r,300));
    // Sina hq - try both markets
    const r2 = await fetch('http://hq.sinajs.cn/list=sz'+code);
    if (r2 && r2.includes('"') && !r2.includes('"",')) {
      const m = r2.match(/"([^"]+)"/);
      if (m) console.log('SZ'+code+':', m[1].split(',')[0]);
    } else {
      const r3 = await fetch('http://hq.sinajs.cn/list=sh'+code);
      if (r3 && r3.includes('"') && !r3.includes('"",')) {
        const m = r3.match(/"([^"]+)"/);
        if (m) console.log('SH'+code+':', m[1].split(',')[0]);
      } else {
        console.log(code + ': 沪深均无实时数据');
      }
    }
    await new Promise(r=>setTimeout(r,300));
  }
}
main();
