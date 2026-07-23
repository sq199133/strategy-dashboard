#!/usr/bin/env node
/**
 * corr_etf.js — ETF相关性计算标准化工具
 *
 * 用途：每次调仓前必须运行，计算ETF两两Pearson相关系数
 * 方法：日收益率序列，120日窗口
 * 阈值：maxCorr ≤ 0.70 才可纳入持仓
 *
 * 用法：
 *   node corr_etf.js [候选代码列表] [现有持仓代码列表]
 *   node corr_etf.js 510500,515070 159681,512770,512220,516390,513100
 *   node corr_etf.js all 159681,512770,512220,516390,513100   # 对所有持仓两两计算
 *
 * 输出：
 *   - 完整相关性矩阵
 *   - 各候选 maxCorr vs 现有持仓
 *   - 通过/排除判定
 */

const https  = require('https');
const path   = require('path');
const fs     = require('fs');

// ── 命令行参数 ────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const rawCandidates = args[0] || '';
const rawHoldings   = args[1] || '';

// 现有持仓（硬编码默认值）
const DEFAULT_HOLDINGS = [
  {market:'sz', code:'159681', name:'创业板50ETF'},
  {market:'sh', code:'512770', name:'战略新兴ETF'},
  {market:'sh', code:'512220', name:'TMTETF'},
  {market:'sz', code:'516390', name:'新能源汽车ETF'},
  {market:'sh', code:'513100', name:'纳指ETF'},
];

// ETF名称映射
const NAME_MAP = {
  'sh510500':'中证500ETF南方','sh512770':'战略新兴ETF华夏','sh512220':'TMTETF景顺',
  'sh159681':'创业板50ETF','sh516390':'新能源汽车ETF','sh513100':'纳指ETF国泰',
  'sh515070':'人工智能ETF华夏','sh159259':'成长ETF','sh159915':'创业板ETF',
  'sh561370':'新能源车ETF','sh159628':'消费电子ETF','sh515220':'新能源ETF',
  'sh562800':'大宗商品ETF','sh518880':'黄金ETF','sh159628':'消费电子ETF',
};

// ── 常量 ───────────────────────────────────────────────────────────────────
const THRESHOLD   = 0.70;   // maxCorr 超过此值 → 排除
const WINDOW      = 120;    // 最多取120日K线
const MIN_DAYS    = 60;     // 共同交易日少于60日 → 数据不足，默认排除
const OUTPUT_FILE = path.join(__dirname, 'data', 'etf_corr_matrix.json');

// ── 工具函数 ───────────────────────────────────────────────────────────────

/** 腾讯接口拉取日K（前复权）*/
function fetchKline(market, code) {
  return new Promise(function(resolve) {
    var fullCode = market + code;
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param='
              + fullCode + ',day,,,' + WINDOW + ',qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var d = '';
      r.on('data', function(s){ d += s; });
      r.on('end', function(){
        try {
          var j = JSON.parse(d.replace(/^[^=]+=/, ''));
          var arr = (j.data[fullCode] && j.data[fullCode].qfqday)
                  || (j.data[fullCode] && j.data[fullCode].day)
                  || [];
          var recs = arr.map(function(p){
            return { date: p[0], close: parseFloat(p[2]) };
          }).filter(function(v){ return v.close > 0; });
          resolve(recs);
        } catch(e) { resolve([]); }
      });
    }).on('error', function(){ resolve([]); });
  });
}

/** Pearson 相关系数 */
function pearson(x, y) {
  if (x.length < 10) return null;
  var n = x.length, mx = 0, my = 0;
  for (var i = 0; i < n; i++) { mx += x[i]; my += y[i]; }
  mx /= n; my /= n;
  var cov = 0, sx = 0, sy = 0;
  for (var i = 0; i < n; i++) {
    var dx = x[i] - mx, dy = y[i] - my;
    cov += dx * dy; sx += dx * dx; sy += dy * dy;
  }
  var den = Math.sqrt(sx * sy);
  return den === 0 ? null : cov / den;
}

/** 日收益率序列 */
function returns(arr) {
  var r = [];
  for (var i = 1; i < arr.length; i++) {
    if (arr[i].close > 0 && arr[i-1].close > 0) {
      r.push((arr[i].close - arr[i-1].close) / arr[i-1].close);
    }
  }
  return r;
}

/** 共同交易日对齐后的收益率 */
function commonReturns(arr1, arr2) {
  var s2 = new Set(arr2.map(function(v){ return v.date; }));
  var r1 = [], r2 = [];
  for (var i = 1; i < arr1.length; i++) {
    if (s2.has(arr1[i].date)) {
      var prev1 = arr1[i-1], curr1 = arr1[i];
      var prev2 = arr2.find(function(v){ return v.date === arr1[i-1].date; });
      if (curr1.close > 0 && prev1.close > 0 && prev2 && prev2.close > 0) {
        r1.push((curr1.close - prev1.close) / prev1.close);
        r2.push((arr2.find(function(v){ return v.date === arr1[i].date; }).close
                 - prev2.close) / prev2.close);
      }
    }
  }
  return { r1: r1, r2: r2, len: r1.length };
}

/** 相关性级别标签 */
function badge(r) {
  if (r === null) return '⚪N/A';
  if (r > 0.85)  return '🔴🔴' + r.toFixed(3);
  if (r > 0.70)  return '🔴' + r.toFixed(3);
  if (r > 0.50)  return '🟡' + r.toFixed(3);
  if (r > 0.30)  return '🟢' + r.toFixed(3);
  return '⚪' + r.toFixed(3);
}

/** 级别描述 */
function desc(r) {
  if (r === null) return '数据不足';
  if (r > 0.85)  return '🔴高度重叠(≈等同)';
  if (r > 0.70)  return '🔴高相关';
  if (r > 0.50)  return '🟡中高相关';
  if (r > 0.30)  return '🟢中低相关';
  return '⚪低相关';
}

// ── 主逻辑 ─────────────────────────────────────────────────────────────────

async function run() {
  // 1. 解析输入
  var candidates = [];
  if (rawCandidates === 'all') {
    // 计算现有持仓两两相关性
    candidates = [];
  } else if (rawCandidates) {
    rawCandidates.split(',').forEach(function(c) {
      c = c.trim();
      if (!c) return;
      var market = c.startsWith('sh') ? 'sh' : c.startsWith('sz') ? 'sz' : 'sh';
      var code   = c.replace(/^(sh|sz)/, '');
      candidates.push({market: market, code: code, name: NAME_MAP[market+code] || market+code});
    });
  }

  var holdings = rawHoldings ? rawHoldings.split(',').map(function(c) {
    c = c.trim();
    if (!c) return null;
    var market = c.startsWith('sh') ? 'sh' : c.startsWith('sz') ? 'sz' : 'sh';
    var code   = c.replace(/^(sh|sz)/, '');
    return {market: market, code: code, name: NAME_MAP[market+code] || market+code};
  }).filter(Boolean) : DEFAULT_HOLDINGS;

  // 合并所有待计算ETF
  var allEtfs = {};
  holdings.forEach(function(e){
    var key = e.market + e.code;
    allEtfs[key] = {market:e.market, code:e.code, name:e.name||NAME_MAP[key]||key, isHolding:true};
  });
  candidates.forEach(function(e){
    var key = e.market + e.code;
    if (!allEtfs[key]) allEtfs[key] = {market:e.market, code:e.code, name:e.name||NAME_MAP[key]||key, isCandidate:true};
    else allEtfs[key].isCandidate = true;
  });

  // 2. 拉取K线
  console.log('━━━ 拉取K线数据 ━━━');
  var data = {};
  var keys  = Object.keys(allEtfs);
  for (var i = 0; i < keys.length; i++) {
    var k  = keys[i];
    var e  = allEtfs[k];
    var recs = await fetchKline(e.market, e.code);
    if (recs.length > 0) {
      data[k] = { name: e.name, recs: recs, rets: returns(recs) };
      console.log('  ✅ ' + (e.name||k).padEnd(14) + ' ' + recs.length + '条 末:' + recs[recs.length-1].date);
    } else {
      data[k] = { name: e.name, recs: [], rets: [] };
      console.log('  ❌ ' + (e.name||k).padEnd(14) + ' 无数据（排除）');
    }
    await new Promise(function(cb){ setTimeout(cb, 400); });
  }

  // 过滤掉无数据的ETF
  var validKeys = keys.filter(function(k){ return data[k].rets.length >= 30; });

  // 3. 构建相关性矩阵
  console.log('\n━━━ Pearson相关矩阵（基于日收益率，' + WINDOW + '日）━━━');
  var matrix = {};
  var h = '代码/名称'.padEnd(16) + ' |';
  validKeys.forEach(function(k){ h += ' ' + (data[k].name||k).substring(0,7).padEnd(9) + '|'; });
  console.log(h);
  console.log('-'.repeat(h.length));

  for (var i = 0; i < validKeys.length; i++) {
    var row = (data[validKeys[i]].name||validKeys[i]).substring(0,14).padEnd(16) + '|';
    for (var j = 0; j < validKeys.length; j++) {
      if (i === j) {
        row += '  1.000   | ';
      } else {
        var r = pearson(data[validKeys[i]].rets, data[validKeys[j]].rets);
        row += ' ' + badge(r) + ' | ';
      }
    }
    console.log(row);
    matrix[validKeys[i]] = {};
    for (var j = 0; j < validKeys.length; j++) {
      if (i !== j) {
        matrix[validKeys[i]][validKeys[j]] = pearson(data[validKeys[i]].rets, data[validKeys[j]].rets);
      }
    }
  }

  console.log('\n图例: 🔴🔴>0.85(≈等同)  🔴>0.70(高)  🟡0.50-0.70(中高)  🟢0.30-0.50(中低)  ⚪<0.30(低)');

  // 4. 候选ETF相关性评估
  if (candidates.length > 0) {
    console.log('\n━━━ 候选ETF相关性评估 ━━━');
    console.log('现有持仓: ' + holdings.map(function(h){ return h.name||(h.market+h.code); }).join(', '));
    console.log('阈值: maxCorr ≤ ' + THRESHOLD + ' → 纳入，maxCorr > ' + THRESHOLD + ' → 排除\n');

    var pass = [], fail = [];

    for (var i = 0; i < candidates.length; i++) {
      var c  = candidates[i];
      var ck = c.market + c.code;
      if (!data[ck] || data[ck].rets.length < 30) {
        console.log('  ❌ ' + (c.name||ck).padEnd(14) + ' → 数据不足（' + (data[ck]?data[ck].rets.length:0) + '条），默认排除');
        fail.push({etf:c, reason:'数据不足'});
        continue;
      }

      // 计算与所有持仓的相关系数
      var corrs = [];
      holdings.forEach(function(h) {
        var hk = h.market + h.code;
        if (data[hk] && data[hk].rets.length >= 30) {
          var cr = commonReturns(data[ck].recs, data[hk].recs);
          var r  = pearson(cr.r1, cr.r2);
          if (r !== null) corrs.push({target: h.name||hk, r: r, days: cr.len});
        }
      });

      var maxCorr = corrs.length > 0 ? Math.max.apply(null, corrs.map(function(x){ return x.r; })) : null;
      var maxTarget = corrs.find(function(x){ return x.r === maxCorr; });
      var passFlag = maxCorr !== null && maxCorr <= THRESHOLD;

      console.log('  ' + (passFlag?'✅':'❌') + ' ' + (c.name||ck).padEnd(14)
        + ' maxCorr=' + (maxCorr!==null?badge(maxCorr):'N/A')
        + ' vs ' + (maxTarget ? maxTarget.target : '无持仓')
        + '  (' + (maxTarget?maxTarget.days+'日':'N/A') + '共同)');

      if (corrs.length > 0) {
        corrs.forEach(function(cr){
          console.log('      └─ vs ' + cr.target.padEnd(12) + ' r=' + badge(cr.r) + ' (' + cr.days + '日)');
        });
      }

      if (passFlag) {
        pass.push({etf:c, maxCorr:maxCorr, maxTarget:maxTarget});
      } else if (maxCorr !== null) {
        fail.push({etf:c, maxCorr:maxCorr, reason:'超过阈值', maxTarget:maxTarget});
      }
    }

    // 5. 汇总
    console.log('\n━━━ 最终判定 ━━━');
    if (pass.length > 0) {
      console.log('✅ 通过相关性审查（可纳入持仓）：');
      pass.forEach(function(p){
        console.log('   ' + (p.etf.name||(p.etf.market+p.etf.code)).padEnd(14)
          + ' maxCorr=' + (p.maxCorr!==null?p.maxCorr.toFixed(3):'N/A')
          + ' vs ' + (p.maxTarget?p.maxTarget.target:'?'));
      });
    } else {
      console.log('❌ 无候选通过相关性审查（maxCorr 均 > ' + THRESHOLD + '）');
    }

    if (fail.length > 0) {
      console.log('\n❌ 排除（超过阈值）：');
      fail.forEach(function(f){
        console.log('   ' + (f.etf.name||(f.etf.market+f.etf.code)).padEnd(14)
          + ' maxCorr=' + (f.maxCorr!==null?f.maxCorr.toFixed(3):'N/A')
          + ' → ' + f.reason + (f.maxTarget?'（最高vs ' + f.maxTarget.target + '）':''));
      });
    }

    // 6. 保存结果
    var result = {
      generated: new Date().toISOString(),
      threshold: THRESHOLD,
      window: WINDOW,
      holdings: holdings.map(function(h){ return {code:(h.market+h.code), name:h.name}; }),
      candidates: candidates.map(function(c){ return {code:(c.market+c.code), name:c.name}; }),
      matrix: matrix,
      passed: pass.map(function(p){ return {
        code: (p.etf.market+p.etf.code),
        name: p.etf.name,
        maxCorr: p.maxCorr,
        vs: p.maxTarget ? p.maxTarget.target : null
      };}),
      failed: fail.map(function(f){ return {
        code: (f.etf.market+f.etf.code),
        name: f.etf.name,
        maxCorr: f.maxCorr,
        reason: f.reason,
        vs: f.maxTarget ? f.maxTarget.target : null
      };})
    };
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(result, null, 2), 'utf8');
    console.log('\n📄 结果已保存: ' + OUTPUT_FILE);
  }
}

run().catch(function(e){ console.error(e); process.exit(1); });
