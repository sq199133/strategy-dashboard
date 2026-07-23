const https = require('https');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fundf10.eastmoney.com/',
      }
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(12000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function main() {
  var code = '510300';
  var url = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=' + code + '&topline=10&year=&month=&rt=0.1';
  var raw = await httpGet(url);
  
  // 打印原始HTML中持仓表格部分
  // 找content:"..."区域
  var m = raw.match(/var apidata=\{[^}]+content:"([^"]+)"/);
  if (m) {
    var content = m[1].replace(/\\n/g,' ').replace(/\\"/g,'"').replace(/\\\'/g,"'");
    console.log('CONTENT LENGTH:', content.length);
    console.log('\n持仓表格区域:');
    // 找table
    var tblMatch = content.match(/<table[\s\S]{0,500}/);
    if (tblMatch) {
      console.log(tblMatch[0].slice(0, 800));
    } else {
      console.log('未找到table，打印前500字符:');
      console.log(content.slice(0, 500));
    }
  } else {
    console.log('未匹配到apidata，打印原始前500:');
    console.log(raw.slice(0, 500));
  }
}

main().catch(console.error);
