const http = require('http');
const fs = require('fs');
const path = require('path');

function fetch(url) {
  return new Promise(resolve => {
    http.get(url, {headers:{
      'User-Agent':'Mozilla/5.0',
      'Referer':'http://finance.sina.com.cn'
    }}, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end',()=>resolve(d));
    }).on('error',()=>resolve(''));
  });
}

async function main() {
  const codes = ['sz159329','sz159100','sz159980','sz159985',
                 'sh159329','sh159100','sh159980','sh159985'];
  
  console.log('===== 实时核实4只ETF =====\n');
  for (const c of codes) {
    const r = await fetch('http://hq.sinajs.cn/list='+c);
    if (r && r.includes('"') && !r.includes('"",')) {
      const m = r.match(/"([^"]+)"/);
      if (m) {
        const fields = m[1].split(',');
        console.log(c.toUpperCase() + ' => ' + fields[0] + ' 昨收=' + fields[2] + ' 当前=' + fields[3]);
      }
    } else {
      console.log(c.toUpperCase() + ' => 无数据');
    }
    await new Promise(r=>setTimeout(r,200));
  }

  // Also search in existing pool files
  const sina = JSON.parse(fs.readFileSync(path.join(__dirname,'sina_etf.json'),'utf8'));
  const em = JSON.parse(fs.readFileSync(path.join(__dirname,'etf_all_raw.json'),'utf8'));
  const emMap = {};
  em.forEach(e => emMap[e.code] = e.size);
  const pool = require('./etf_pool_v4.js');
  const poolCodes = new Set(pool.map(e=>e.code));
  
  const targets = ['159329','159100','159980','159985'];
  console.log('\n===== 在现有数据中的匹配 =====\n');
  targets.forEach(code => {
    const s = sina.find(e=>e.code===code);
    const size = emMap[code];
    const inPool = poolCodes.has(code);
    const sector = s ? s.name : '❌不在新浪ETF列表';
    console.log(code + ': ' + sector + ' | EM规模=' + (size||'?') + '亿 | 已在池=' + inPool);
  });
}
main();
