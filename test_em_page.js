const https = require('https');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://fundf10.eastmoney.com/'
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

async function parseFundPage(code) {
  var url = 'https://fundf10.eastmoney.com/' + code + '.html';
  var html = await httpGet(url);

  // 提取跟踪指数
  var trackMatch = html.match(/跟踪指数[\s\S]{0,50}?<[^>]+>([^<]{2,50})/);
  var trackName  = trackMatch ? trackMatch[1].trim().replace(/&nbsp;/g,' ').replace(/<[^>]+>/g,'') : '';

  // 提取跟踪指数代码
  var trackCodeMatch = html.match(/指数代码[：:\s]*([0-9A-Za-z]{6,10})/);
  var trackCode = trackCodeMatch ? trackCodeMatch[1].trim() : '';

  // 提取重仓股（从持仓表格）
  var holdings = [];
  // 找重仓股区域
  var secHoldMatch = html.match(/前十大重仓股[\s\S]{0,3000}?<\/table>/);
  if (secHoldMatch) {
    var block = secHoldMatch[0];
    // 匹配股票代码和名称
    var stockMatches = block.matchAll(/>([0-9]{6})<\/a>[\s\S]{0,100}?title="([^"]+)"/g);
    for (var m of stockMatches) {
      holdings.push({ code: m[1], name: m[2] });
      if (holdings.length >= 10) break;
    }
    // 备选：匹配表格内数据
    if (holdings.length === 0) {
      var tdMatches = block.matchAll(/<td[^>]*>([^<]{2,15})<\/td>/g);
      var items = [];
      for (var t of tdMatches) items.push(t[1]);
      // 每3个一组：名称/代码/占比
      for (var i = 0; i < items.length - 2; i += 3) {
        if (items[i].match(/^[0-9]{6}/)) {
          holdings.push({ code: items[i], name: items[i+1] || '' });
        }
      }
    }
  }

  // 提取规模
  var scaleMatch = html.match(/基金规模[：:\s]*([0-9.]+)[\u4e00-\u9fa5]*亿/);
  var scale = scaleMatch ? scaleMatch[1] : '';

  return {
    code: code,
    trackName: trackName,
    trackCode: trackCode,
    holdings: holdings.slice(0, 10),
    scale: scale,
    rawSnippet: html.slice(0, 500) // 前500字调试用
  };
}

async function main() {
  var tests = ['510300', '159915', '513100', '588000', '512880'];
  console.log('测试东方财富基金页面解析...\n');

  for (var code of tests) {
    process.stdout.write(code + ' ... ');
    try {
      var result = await parseFundPage(code);
      console.log('\n  跟踪指数: ' + result.trackName + ' (' + result.trackCode + ')');
      console.log('  规模: ' + result.scale + '亿');
      console.log('  前10持仓: ' + result.holdings.map(h=>h.name+'('+h.code+')').join(', ') || '未提取到');
      console.log('  原始片断: ' + result.rawSnippet.match(/跟踪指数[\s\S]{0,100}/)?.[0]?.slice(0,150) || '');
    } catch(e) {
      console.log('ERR: ' + e.message);
    }
    await new Promise(r => setTimeout(r, 800));
  }
}

main().catch(console.error);
