// fetch_etf_holdings.js
// 东方财富基金持仓接口：批量获取ETF前10大成份股，用于计算持仓相似度
const https = require('https');
const fs   = require('fs');
const path = require('path');

const ALL_ETFS = require('./data/etf_pool.js');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://fundf10.eastmoney.com/',
        'Accept': '*/*'
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

async function getHoldings(code) {
  var url = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=' + code + '&topline=10&year=&month=&rt=0.1';
  var raw = await httpGet(url);

  // 提取 content:"..."
  var m = raw.match(/var apidata=\{[^}]+content:"([^"]+)"/);
  if (!m) return [];
  var content = m[1]
    .replace(/\\n/g,' ').replace(/\\"/g,'"').replace(/\\\'/g,"'")
    .replace(/&#x27;/g, "'").replace(/&nbsp;/g,' ')
    .replace(/&lt;/g,'<').replace(/&gt;/g,'>');

  // 提取每行 tr
  var holdings = [];
  var rowMatches = content.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi);
  var rowCount = 0;
  for (var row of rowMatches) {
    var rowHtml = row[1];
    // 跳过表头
    if (rowHtml.includes('<th')) continue;
    rowCount++;
    if (rowCount > 10) break;

    // 提取股票代码: //quote.eastmoney.com/unify/r/0.XXXXXX
    var codeMatch = rowHtml.match(/unify\/r\/0\.(\d{6})/);
    // 提取股票名称 (td.tol 内的 a 的 title 或 text)
    var nameMatch = rowHtml.match(/class='tol'><a[^>]+>([^<]+)<\/a>/);
    // 提取占净值比例
    var weightMatch = rowHtml.match(/占净值<br\s*\/?>[\s\S]{0,50}?<td[^>]*>([^<]+)<\/td>/);
    var ratioMatch = rowHtml.match(/class='cgs[^']*'>([^<]+)<\/td>/);

    if (codeMatch) {
      holdings.push({
        stockCode:   codeMatch[1],
        stockName:   nameMatch ? nameMatch[1].trim() : '',
        ratio:       weightMatch ? weightMatch[1].trim() : ''
      });
    }
  }
  return holdings;
}

// ── 计算两只ETF的持仓相似度（Jaccard + 加权重叠）───────────
function calcSimilarity(a, b) {
  if (!a.length || !b.length) return 0;

  // 集合A和B
  var setA = new Set(a.map(x => x.stockCode));
  var setB = new Set(b.map(x => x.stockCode));

  // Jaccard: |A∩B| / |A∪B|
  var intersection = [...setA].filter(x => setB.has(x)).length;
  var union = new Set([...setA, ...setB]).size;
  var jaccard = intersection / union;

  // 加权重叠: 按持仓权重计算
  var weightSum = 0;
  a.forEach(function(x){
    var match = b.find(function(y){ return y.stockCode === x.stockCode; });
    if (match) {
      weightSum += Math.min(parseFloat(x.ratio)||0, parseFloat(match.ratio)||0);
    }
  });
  var maxWeight = (a.reduce(function(s,x){return s+(parseFloat(x.ratio)||0);},0) +
                   b.reduce(function(s,x){return s+(parseFloat(x.ratio)||0);},0)) / 2;
  var weighted = maxWeight > 0 ? weightSum / maxWeight : 0;

  return { jaccard: +jaccard.toFixed(3), weighted: +weighted.toFixed(3), common: intersection };
}

async function main() {
  console.log('开始抓取ETF持仓数据（东方财富）...');
  console.log('总计: ' + ALL_ETFS.length + ' 只\n');

  var results = {};
  var errors  = [];

  for (var i = 0; i < ALL_ETFS.length; i++) {
    var etf = ALL_ETFS[i];
    process.stdout.write('[' + String(i+1).padStart(3) + '/' + ALL_ETFS.length + '] ' + etf.code + ' ' + etf.name.slice(0,8) + ' ... ');

    try {
      var holdings = await getHoldings(etf.code);
      results[etf.code] = {
        code:     etf.code,
        name:     etf.name,
        market:   etf.market,
        category: etf.category,
        size:     etf.size,
        holdings: holdings
      };
      if (holdings.length > 0) {
        console.log('  ' + holdings.length + '只: ' + holdings.map(h=>h.stockName).join(',').slice(0,60));
      } else {
        console.log('  (无持仓数据)');
      }
    } catch(e) {
      errors.push({ code: etf.code, name: etf.name, err: e.message });
      console.log('  ERR: ' + e.message);
    }

    if ((i+1) % 30 === 0) {
      console.log('\n--- 暂停3秒 ---');
      await new Promise(r => setTimeout(r, 3000));
    } else {
      await new Promise(r => setTimeout(r, 200));
    }
  }

  // ── 按持仓相似度去重 ──────────────────────────────
  // 只用有持仓数据的ETF
  var codes = Object.keys(results).filter(function(k){
    return results[k].holdings && results[k].holdings.length > 0;
  });
  console.log('\n\n有持仓数据: ' + codes.length + ' 只\n');

  // 计算两两相似度矩阵
  var sim = {};
  for (var i = 0; i < codes.length; i++) {
    for (var j = i+1; j < codes.length; j++) {
      var key = codes[i] + '|' + codes[j];
      var s = calcSimilarity(results[codes[i]].holdings, results[codes[j]].holdings);
      if (s.jaccard > 0) {  // 只记录有交集的
        sim[key] = s;
      }
    }
  }

  // 按相似度降序排列
  var pairs = Object.entries(sim)
    .map(function(e){ return {pair:e[0], ...e[1]}; })
    .filter(function(x){ return x.jaccard > 0; })
    .sort(function(a,b){ return b.jaccard - a.jaccard; });

  console.log('━━━━━━━ 持仓高度相似ETF对（jaccard≥0.2）━━━━━━━');
  pairs.filter(function(p){ return p.jaccard >= 0.2; }).forEach(function(p) {
    var [c1,c2] = p.pair.split('|');
    console.log('  ' + p.jaccard + ' / ' + p.weighted + '  |  ' +
      results[c1].name + '(' + c1 + ')' + ' vs ' + results[c2].name + '(' + c2 + ')' +
      '  |  共同持仓: ' + p.common + '只');
  });

  // ── 贪心去重：每组保留规模最大的 ──────────────
  // 合并所有高度相似的ETF对
  var DSU = function(n) {
    this.parent = Array.from({length:n}, (_,i)=>i);
    this.find = function(x){ return this.parent[x]===x?x:(this.parent[x]=this.find(this.parent[x])); };
    this.union = function(a,b){ this.parent[this.find(a)] = this.find(b); };
  };

  var idx = codes.map(function(c){return c;});
  var dsu = new DSU(codes.length);
  pairs.filter(function(p){ return p.jaccard >= 0.3; }).forEach(function(p) {
    var [c1,c2] = p.pair.split('|');
    var i1 = idx.indexOf(c1), i2 = idx.indexOf(c2);
    if (i1>=0 && i2>=0) dsu.union(i1, i2);
  });

  // 找每个组的最大规模ETF
  var groups = {};
  codes.forEach(function(c) {
    var root = dsu.find(idx.indexOf(c));
    if (!groups[root]) groups[root] = [];
    groups[root].push(results[c]);
  });

  console.log('\n━━━━━━━ 去重分组结果（jaccard≥0.3归为同组）━━━━━━━');
  var toKeep = [], removed = [];
  Object.values(groups).forEach(function(group) {
    group.sort(function(a,b){ return (b.size||0) - (a.size||0); });
    console.log('\n组内 ' + group.length + ' 只（同持仓高度重叠）:');
    group.forEach(function(e, i) {
      var mark = i===0 ? ' ✅ KEEP' : ' ❌ REMOVE';
      console.log('  ' + mark + '  ' + e.code + ' ' + e.name + '  规模:' + e.size + '亿');
    });
    toKeep.push(group[0]);
    if (group.length > 1) removed.push(...group.slice(1));
  });

  var noHoldings = ALL_ETFS.filter(function(e){ return !results[e.code] || !results[e.code].holdings.length; });
  console.log('\n━━━━━━━ 最终去重结果 ━━━━━━━');
  console.log('保留: ' + toKeep.length + ' 只（含无持仓数据但规模大的: ' +
    toKeep.filter(function(e){ return !e.holdings.length; }).length + ' 只）');
  console.log('剔除: ' + removed.length + ' 只');
  console.log('无持仓数据: ' + noHoldings.length + ' 只');

  // 合并：保留有持仓的 + 无持仓但不在任何组里的
  var removedCodes = new Set(removed.map(function(e){return e.code;}));
  var allKept = [
    ...toKeep,
    ...noHoldings.filter(function(e){ return !removedCodes.has(e.code); })
  ];

  console.log('\n最终ETF池: ' + allKept.length + ' 只');

  // 保存中间结果
  fs.writeFileSync(path.join(__dirname,'data','etf_holdings_raw.json'), JSON.stringify(results,null,2),'utf8');
  fs.writeFileSync(path.join(__dirname,'data','etf_similarity_pairs.json'), JSON.stringify(pairs,null,2),'utf8');
  fs.writeFileSync(path.join(__dirname,'data','etf_pool_dedup_candidates.json'),
    JSON.stringify({keep:toKeep,remove:removed,noHoldings:noHoldings,finalList:allKept},null,2),'utf8');

  console.log('\n[OK] data/etf_holdings_raw.json        (持仓原始数据)');
  console.log('[OK] data/etf_similarity_pairs.json    (相似度矩阵)');
  console.log('[OK] data/etf_pool_dedup_candidates.json (去重候选名单)');
  console.log('\n请确认后，我将用保留名单更新 etf_pool.js 和 scripts/scan/etf_pool.json');
}

main().catch(console.error);
