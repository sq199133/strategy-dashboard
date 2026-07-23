// Verify the actual 5 holdings in real-time
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
  const codes = ['sz159681','sz512770','sz512220','sz516390','sz513100',
                 'sh159681','sh512770','sh512220','sh516390','sh513100'];
  
  console.log('===== 实时验证5只持仓 =====\n');
  for (const c of codes) {
    const r = await fetch('http://hq.sinajs.cn/list='+c);
    if (r && r.includes('"') && !r.includes('"".*""')) {
      // Parse: var hq_str_xxx="name,price,prev_close,open,high,low,..."
      const m = r.match(/"([^"]+)"/);
      if (m) {
        const fields = m[1].split(',');
        console.log(c.toUpperCase() + ' => 名称=' + fields[0] + ' 当前价=' + fields[3] + ' 昨收=' + fields[2]);
      }
    } else {
      console.log(c.toUpperCase() + ' => 无数据或停牌');
    }
    await new Promise(r=>setTimeout(r,200));
  }
  
  // Also check the Sina ETF list for any codes we might have missed
  const sina = JSON.parse(fs.readFileSync(path.join(__dirname,'sina_etf.json'),'utf8'));
  
  // Check all our holdings
  const holdings = ['159681','512770','512220','516390','513100'];
  console.log('\n===== 新浪ETF列表搜索持仓 =====\n');
  holdings.forEach(code => {
    const found = sina.find(e => e.code === code);
    console.log(code + ': ' + (found ? found.name + ' ✅' : '❌ 不在ETF列表（可能为LOF/普通基金）'));
  });
  
  // Try EM historical for 516390
  console.log('\n===== 尝试东方财富历史数据 =====');
  // EM 5min kline for 2026-04-17
  const r = await fetch('http://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.516390&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56&klt=15&fqt=1&beg=20260417&end=20260418');
  if (r) {
    try {
      const j = JSON.parse(r);
      if (j.data?.klines) {
        console.log('EM 516390:');
        j.data.klines.slice(0,5).forEach(l => console.log('  '+l));
      } else {
        console.log('EM 516390: 无历史数据（可能已退市/改名）');
      }
    } catch(e) { console.log('EM parse error'); }
  }
}
main();
