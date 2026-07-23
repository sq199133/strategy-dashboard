// ETF池去重脚本 - 按跟踪指数去重，保留最优标的
var fs = require('fs');
var POOL_FILE = 'D:/QClaw_Trading/data/etf_pool.js';
var pool = require(POOL_FILE);

console.log('去重前：' + pool.length + '只\n');

// 分组（同上）
var groups = {};
pool.forEach(function(e) {
  var name = e.name;
  var key = null;
  
  if (name.includes('上证50') || name === '50ETF') key = '上证50';
  else if (name.includes('沪深300')) key = '沪深300';
  else if (name.includes('中证A500') || name.includes('A500')) key = '中证A500';
  else if (name.includes('中证500') || name.includes('500ETF')) key = '中证500';
  else if (name.includes('中证1000') || name.includes('1000ETF')) key = '中证1000';
  else if (name.includes('中证100')) key = '中证100';
  else if (name.includes('创业板') || name.includes('创业板指')) key = '创业板指';
  else if (name.includes('科创50') || name === '科创50ETF') key = '科创50';
  else if (name.includes('科创100')) key = '科创100';
  else if (name.includes('深证50') || name.includes('深50')) key = '深证50';
  else if (name.includes('深100')) key = '深证100';
  else if (name.includes('证券')) key = '证券';
  else if (name.includes('银行')) key = '银行';
  else if (name.includes('保险')) key = '保险';
  else if (name.includes('地产') || name.includes('房地产')) key = '房地产';
  else if (name.includes('消费') && !name.includes('医药')) key = '消费';
  else if (name.includes('医药') || name.includes('医疗') || name.includes('生物')) key = '医药医疗';
  else if (name.includes('中药')) key = '中药';
  else if (name.includes('半导体') || name.includes('芯片') || name.includes('科创芯')) key = '半导体芯片';
  else if (name.includes('通信') || name.includes('5G')) key = '通信';
  else if (name.includes('人工智能') || name.includes('AI')) key = '人工智能';
  else if (name.includes('科技') && !name.includes('恒生')) key = '科技';
  else if (name.includes('军工') || name.includes('航天')) key = '军工';
  else if (name.includes('机器人')) key = '机器人';
  else if (name.includes('新能源车') || name.includes('电动车')) key = '新能源车';
  else if (name.includes('光伏') || name.includes('储能') || name.includes('电池')) key = '光伏储能';
  else if (name.includes('新能源') || name.includes('能源')) key = '新能源';
  else if (name.includes('稀土') || name.includes('有色') || name.includes('稀有金属')) key = '有色稀土';
  else if (name.includes('钢铁')) key = '钢铁';
  else if (name.includes('煤炭')) key = '煤炭';
  else if (name.includes('红利低波')) key = '红利低波';
  else if (name.includes('红利') && !name.includes('央企')) key = '红利';
  else if (name.includes('央企')) key = '央企';
  else if (name.includes('成长')) key = '成长';
  else if (name.includes('纳指') || name.includes('纳斯达克')) key = '纳斯达克100';
  else if (name.includes('标普') || name.includes('S&P')) key = '标普500';
  else if (name.includes('道琼斯') || name.includes('道指')) key = '道琼斯';
  else if (name.includes('恒生科技')) key = '恒生科技';
  else if (name.includes('恒生互联') || name.includes('中概互联') || name.includes('恒生互联网')) key = '中概互联';
  else if (name.includes('恒生指数') || name.includes('恒指') || name.includes('恒生ETF')) key = '恒生指数';
  else if (name.includes('日经')) key = '日经225';
  else if (name.includes('德国')) key = '德国DAX';
  else if (name.includes('港股创新药')) key = '港股创新药';
  else if (name.includes('恒生医疗')) key = '恒生医疗';
  else if (name.includes('黄金') || name.includes('上海金')) key = '黄金';
  else if (name.includes('豆粕')) key = '豆粕';
  else if (name.includes('原油') || name.includes('能源化工')) key = '原油化工';
  else if (name.includes('国债')) key = '国债';
  else if (name.includes('信用债')) key = '信用债';
  else if (name.includes('卫星')) key = '卫星';
  else key = '其他-' + e.code;
  
  if (!groups[key]) groups[key] = [];
  groups[key].push(e);
});

// 无规模数据时的人工优先列表（流动性最好/最知名）
var MANUAL_KEEP = {
  '上证50': '510050',      // 华夏上证50ETF，最老最活跃
  '中概互联': '513050',    // 易方达中概互联
  '医药医疗': '512170',    // 华宝医疗ETF，最活跃
  '国债': '511010',        // 国债ETF
  '德国DAX': '513030',     // 华安德国DAX
  '日经225': '513000',     // 易方达日经225
  '消费': '159928',        // 消费ETF
  '恒生科技': '513180',    // 华夏恒生科技
  '红利': '510880',        // 华泰柏瑞红利ETF
  '纳斯达克100': '513100', // 国泰纳指ETF
  '银行': '512800',        // 银行ETF
  '黄金': '518880',        // 华安黄金ETF
  '创业板指': '159915',    // 创业板ETF
  '证券': '512880',        // 国泰证券ETF
  '豆粕': '159985',        // 豆粕ETF
  '能源': '520580',        // 能源化工ETF
  '央企红利': '159332',    // 央企红利
};

// 去重
var keepCodes = new Set();
var removeList = [];

Object.keys(groups).forEach(function(key) {
  var list = groups[key];
  
  if (list.length === 1) {
    // 无重复，直接保留
    keepCodes.add(list[0].code);
    return;
  }
  
  // 有重复，选择保留哪个
  var keep = null;
  
  // 1. 优先按规模排序
  var withSize = list.filter(function(e) { return e.size > 0; });
  if (withSize.length > 0) {
    withSize.sort(function(a, b) { return b.size - a.size; });
    keep = withSize[0];
  }
  
  // 2. 无规模时用人工优先列表
  if (!keep && MANUAL_KEEP[key]) {
    keep = list.find(function(e) { return e.code === MANUAL_KEEP[key]; });
  }
  
  // 3. 还是没有，选第一个
  if (!keep) {
    keep = list[0];
  }
  
  keepCodes.add(keep.code);
  
  // 记录剔除的
  list.forEach(function(e) {
    if (e.code !== keep.code) {
      removeList.push({
        key: key,
        code: e.code,
        name: e.name,
        reason: keep.code + ' (' + (keep.size || '无规模') + ')'
      });
    }
  });
});

// 输出去重结果
console.log('=== 去重结果 ===\n');
console.log('保留：' + keepCodes.size + '只');
console.log('剔除：' + removeList.length + '只\n');

// 按组显示剔除
var byGroup = {};
removeList.forEach(function(r) {
  if (!byGroup[r.key]) byGroup[r.key] = {keep: r.reason, remove: []};
  byGroup[r.key].remove.push(r.code + ' ' + r.name);
});

Object.keys(byGroup).sort().forEach(function(key) {
  var g = byGroup[key];
  console.log('【' + key + '】保留：' + g.keep);
  g.remove.forEach(function(r) { console.log('  剔除：' + r); });
  console.log('');
});

// 生成新池
var newPool = pool.filter(function(e) { return keepCodes.has(e.code); });

// 保存
var jsContent = '// ETF池 v4.4 - 去重后 ' + newPool.length + '只\n'
  + '// 更新日期: ' + new Date().toISOString().slice(0, 10) + '\n'
  + '// 剔除' + removeList.length + '只重复标的\n'
  + 'module.exports = ' + JSON.stringify(newPool, null, 2) + ';\n';
fs.writeFileSync(POOL_FILE, jsContent, 'utf8');

console.log('\n=== 完成 ===');
console.log('去重前：' + pool.length + '只');
console.log('去重后：' + newPool.length + '只');
console.log('已保存：' + POOL_FILE);
