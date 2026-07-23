// test_sina_single.js - 测试单只ETF的新浪API返回
const https = require('https');

const symbol = process.argv[2] || 'sh510880'; // 红利ETF，之前失败的

function fetchSina(symbol, datalen) {
  return new Promise((resolve, reject) => {
    const url = `https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=${symbol}&scale=240&ma=no&datalen=${datalen}`;
    console.log('URL:', url);
    
    const req = https.get(url, {
      headers: {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0'
      },
      timeout: 15000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, data: data.trim() }));
    });
    
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('timeout'));
    });
  });
}

async function test() {
  console.log('=== 测试新浪API ===');
  console.log('代码:', symbol);
  console.log('');
  
  try {
    const { status, data } = await fetchSina(symbol, 10);
    console.log('HTTP状态:', status);
    console.log('返回长度:', data.length);
    console.log('返回内容（前500字符）:');
    console.log(data.substring(0, 500));
    console.log('');
    
    if (data === 'null' || data === '') {
      console.log('⚠️ API返回 null 或空');
    } else {
      try {
        const json = JSON.parse(data);
        console.log('✅ JSON解析成功，条数:', json.length);
        if (json.length > 0) {
          console.log('样例:', JSON.stringify(json[0], null, 2));
        }
      } catch(e) {
        console.log('❌ JSON解析失败:', e.message);
      }
    }
  } catch(e) {
    console.log('❌ 请求失败:', e.message);
  }
}

test();
