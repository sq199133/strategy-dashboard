const https = require('https');

function httpGet(url, referer) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': referer || 'https://fundf10.eastmoney.com/',
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

// 东方财富基金持仓接口
async function getHoldings(code) {
  var url = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=' + code + '&topline=10&year=&month=&rt=0.1';
  var raw = await httpGet(url);

  // 提取 content 内容
  var m = raw.match(/var apidata=\{[^}]+content:"([^"]+)"/);
  if (!m) return null;
  var content = m[1].replace(/\\n/g,' ').replace(/\\"/g,'"').replace(/\\\'/g,"'");

  // 解析HTML中的股票表格
  var holdings = [];
  // 匹配 <td>股票代码</td><td>股票名称</td>...结构
  var rowMatches = content.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi);
  for (var row of rowMatches) {
    var rowHtml = row[1];
    // 提取股票代码（6位数字）
    var codeMatch = rowHtml.match(/">(\d{6})<\/a>/);
    // 提取股票名称
    var nameMatch = rowHtml.match(/title="([^"]+)"/);
    if (codeMatch) {
      holdings.push({ code: codeMatch[1], name: nameMatch ? nameMatch[1] : '' });
    }
  }

  return holdings;
}

// 东方财富基金基本信息接口（含跟踪指数）
async function getFundInfo(code) {
  // 尝试emapi接口
  var apis = [
    // 天天基金基本信息
    'https://hxfund.eastmoney.com/FundMapi/FundInfo/BaseInfo?fundCode=' + code,
    // 东方财富旧接口
    'https://fundf10.eastmoney.com/jjbx/' + code + '.html',
  ];

  for (var url of apis) {
    try {
      var raw = await httpGet(url);
      // 找跟踪指数
      var trackMatch = raw.match(/跟踪指数[：:\s\u00A0]*<[^>]+>([^<]{2,50})/);
      if (trackMatch) return { track: trackMatch[1].trim() };

      // 备选：从HTML中提取
      var track2 = raw.match(/跟踪指数[：:\s]*([^\s<]{2,40})/);
      if (track2) return { track: track2[1].trim() };

      // 看看页面里有什么关键词
      if (raw.includes('跟踪指数')) {
        var idx = raw.indexOf('跟踪指数');
        return { raw: raw.slice(idx, idx+200) };
      }
    } catch(e) {}
  }
  return null;
}

async function main() {
  var tests = [
    {code:'510300', name:'沪深300ETF华泰'},
    {code:'510310', name:'沪深300ETF易方达'},
    {code:'159919', name:'沪深300ETF嘉实'},
    {code:'512880', name:'证券ETF'},
    {code:'159915', name:'创业板ETF易方达'},
    {code:'512760', name:'芯片ETF'},
    {code:'513100', name:'纳指ETF国泰'},
    {code:'588000', name:'科创50ETF华夏'},
  ];

  console.log('测试东方财富基金持仓API...\n');

  for (var t of tests) {
    process.stdout.write(t.code + ' ' + t.name + ' ... ');
    try {
      var holdings = await getHoldings(t.code);
      if (holdings && holdings.length > 0) {
        console.log('\n  持仓(' + holdings.length + '):', holdings.map(h=>h.code+'/'+h.name).join(', '));
      } else {
        console.log('无持仓数据');
      }
    } catch(e) {
      console.log('ERR:', e.message);
    }

    // 顺便测试跟踪指数
    try {
      var info = await getFundInfo(t.code);
      if (info && info.track) {
        console.log('  跟踪指数: ' + info.track);
      } else if (info && info.raw) {
        console.log('  跟踪指数(片断): ' + info.raw);
      }
    } catch(e) {}

    await new Promise(r => setTimeout(r, 600));
  }
}

main().catch(console.error);
