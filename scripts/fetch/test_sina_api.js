// test_sina_api.js - 测试新浪API能否获取完整历史
const https = require('https');
const http = require('http');
const fs = require('fs');

const symbol = process.argv[2] || 'sh510300';

function fetchSina(symbol, datalen) {
  return new Promise((resolve, reject) => {
    const url = `https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=${symbol}&scale=240&ma=no&datalen=${datalen}`;
    console.log('请求URL:', url);
    
    https.get(url, {
      headers: {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0'
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

async function test() {
  console.log('=== 测试新浪API ===');
  console.log('代码:', symbol);
  console.log('');
  
  // 测试不同的datalen
  const testLens = [10, 100, 1000, 5000, 10000];
  
  for (const len of testLens) {
    console.log(`\n测试 datalen=${len}...`);
    try {
      const raw = await fetchSina(symbol, len);
      console.log('返回长度:', raw.length);
      
      if (raw.length > 0 && raw !== 'null') {
        const json = JSON.parse(raw);
        if (Array.isArray(json)) {
          console.log(`✅ 成功获取 ${json.length} 条`);
          if (json.length > 0) {
            console.log(`   最早: ${json[json.length-1].day}`);
            console.log(`   最新: ${json[0].day}`);
          }
          // 保存到文件
          fs.writeFileSync(`D:\\QClaw_Trading\\data\\test_sina_${symbol}_${len}.json`, JSON.stringify(json, null, 2));
        } else {
          console.log('⚠️ 返回不是数组:', typeof json);
        }
      } else {
        console.log('⚠️ 返回为空或null');
      }
    } catch(e) {
      console.log('❌ 失败:', e.message);
    }
    
    // 延迟
    await new Promise(r => setTimeout(r, 1000));
  }
}

test();
