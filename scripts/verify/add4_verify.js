const http = require('http');
const fs = require('fs');
const { execSync } = require('child_process');

function fetch(url, headers={}) {
  return new Promise(resolve => {
    http.get(url, {headers:{'User-Agent':'Mozilla/5.0',...headers}}, res => {
      let d=Buffer.alloc(0);
      res.on('data',c=>d=Buffer.concat([d,c]));
      res.on('end',()=>resolve(d));
    }).on('error',()=>resolve(Buffer.alloc(0)));
  });
}

async function main() {
  const codes = ['sz159329','sz159100','sz159980','sz159985','sh159329','sh159100','sh159980','sh159985'];
  const results = {};
  
  for (const c of codes) {
    const r = await fetch('http://hq.sinajs.cn/list='+c,{'Referer':'http://finance.sina.com.cn'});
    const text = r.toString('gbk');
    if (text.includes('"') && !text.includes('"",')) {
      const m = text.match(/"([^"]+)"/);
      if (m) {
        const name = m[1].split(',')[0];
        const price = m[1].split(',')[3];
        const prev = m[1].split(',')[2];
        const key = c.replace('sz','').replace('sh','');
        if (!results[key] || results[key].name !== name) {
          results[key] = { name, price, prev, market: c.startsWith('sz')?'SZ':'SH' };
        }
      }
    }
    await new Promise(r=>setTimeout(r,200));
  }
  
  // Try EM for remaining
  for (const code of Object.keys(results)) {
    if (!results[code].size) {
      const r2 = await fetch('http://fundgz.1234567.com.cn/js/'+code+'.js?rt=1');
      const t = r2.toString('utf8');
      if (t.includes('jsonpgz') && !t.includes('jsonpgz();')) {
        const m = t.match(/"gsz":"([^"]+)"/);
        if (m) results[code].gsz = m[1];
      }
    }
  }
  
  fs.writeFileSync('C:\\Users\\沈强\\.qclaw\\workspace\\trading\\new4_verify.json', JSON.stringify(results,null,2));
  console.log(JSON.stringify(results, null, 2));
}
main();
