// 分析ETF池中的重复标的（跟踪同一指数）
var fs = require('fs');
var POOL_FILE = 'D:/QClaw_Trading/data/etf_pool.js';
var pool = require(POOL_FILE);

console.log('ETF池总数：' + pool.length + '只\n');

// 按关键词分组（同一指数/主题）
var groups = {};

// 分组规则：名称中的关键词
pool.forEach(function(e) {
  var name = e.name;
  var key = null;
  
  // 宽基指数
  if (name.includes('上证50') || name === '50ETF') key = '上证50';
  else if (name.includes('沪深300')) key = '沪深300';
  else if (name.includes('中证500') || name.includes('500ETF')) key = '中证500';
  else if (name.includes('中证1000') || name.includes('1000ETF')) key = '中证1000';
  else if (name.includes('中证100')) key = '中证100';
  else if (name.includes('中证A500') || name.includes('A500')) key = '中证A500';
  else if (name.includes('创业板') || name.includes('创业板指')) key = '创业板指';
  else if (name.includes('科创50') || name === '科创50ETF') key = '科创50';
  else if (name.includes('科创100')) key = '科创100';
  else if (name.includes('深证50') || name.includes('深50')) key = '深证50';
  else if (name.includes('深100')) key = '深证100';
  
  // 行业主题
  else if (name.includes('证券')) key = '证券';
  else if (name.includes('银行')) key = '银行';
  else if (name.includes('保险')) key = '保险';
  else if (name.includes('地产') || name.includes('房地产')) key = '房地产';
  else if (name.includes('消费')) key = '消费';
  else if (name.includes('医药') || name.includes('医疗') || name.includes('生物')) key = '医药医疗';
  else if (name.includes('中药')) key = '中药';
  else if (name.includes('半导体') || name.includes('芯片') || name.includes('科创芯')) key = '半导体芯片';
  else if (name.includes('通信') || name.includes('5G')) key = '通信';
  else if (name.includes('人工智能') || name.includes('AI')) key = '人工智能';
  else if (name.includes('科技')) key = '科技';
  else if (name.includes('军工') || name.includes('航天')) key = '军工';
  else if (name.includes('机器人')) key = '机器人';
  else if (name.includes('新能源') || name.includes('光伏') || name.includes('储能') || name.includes('电池')) key = '新能源';
  else if (name.includes('新能源车') || name.includes('电动车')) key = '新能源车';
  else if (name.includes('稀土') || name.includes('有色') || name.includes('稀有金属')) key = '有色稀土';
  else if (name.includes('钢铁')) key = '钢铁';
  else if (name.includes('煤炭')) key = '煤炭';
  else if (name.includes('能源')) key = '能源';
  
  // 策略指数
  else if (name.includes('红利') && !name.includes('央企')) key = '红利';
  else if (name.includes('红利低波')) key = '红利低波';
  else if (name.includes('央企')) key = '央企';
  else if (name.includes('成长')) key = '成长';
  
  // 跨境
  else if (name.includes('纳指') || name.includes('纳斯达克')) key = '纳斯达克100';
  else if (name.includes('标普') || name.includes('S&P')) key = '标普500';
  else if (name.includes('道琼斯') || name.includes('道指')) key = '道琼斯';
  else if (name.includes('恒生科技')) key = '恒生科技';
  else if (name.includes('恒生互联') || name.includes('中概互联')) key = '中概互联';
  else if (name.includes('恒生指数') || name.includes('恒指')) key = '恒生指数';
  else if (name.includes('日经')) key = '日经225';
  else if (name.includes('德国')) key = '德国DAX';
  else if (name.includes('港股创新药')) key = '港股创新药';
  else if (name.includes('恒生医疗')) key = '恒生医疗';
  
  // 商品
  else if (name.includes('黄金') || name.includes('上海金')) key = '黄金';
  else if (name.includes('豆粕')) key = '豆粕';
  else if (name.includes('原油') || name.includes('能源化工')) key = '原油化工';
  
  // 债券
  else if (name.includes('国债')) key = '国债';
  else if (name.includes('信用债')) key = '信用债';
  
  else key = '其他-' + name.substring(0, 4);
  
  if (!groups[key]) groups[key] = [];
  groups[key].push(e);
});

// 输出分组结果
console.log('=== 按跟踪指数/主题分组 ===\n');

var duplicates = [];
Object.keys(groups).sort().forEach(function(key) {
  var list = groups[key];
  if (list.length > 1) {
    duplicates.push({key: key, count: list.length, etfs: list});
    console.log('【' + key + '】' + list.length + '只：');
    list.forEach(function(e) {
      var size = e.size ? e.size + '亿' : '无规模';
      console.log('  ' + e.code + ' ' + e.name + ' (' + size + ')');
    });
    console.log('');
  }
});

console.log('\n=== 重复统计 ===');
console.log('有重复的指数/主题：' + duplicates.length + '个');
console.log('涉及ETF：' + duplicates.reduce(function(s, d) { return s + d.count; }, 0) + '只');

// 建议保留（按规模最大）
console.log('\n=== 去重建议（保留规模最大） ===');
duplicates.forEach(function(d) {
  var sorted = d.etfs.filter(function(e) { return e.size > 0; }).sort(function(a, b) { return b.size - a.size; });
  if (sorted.length > 0) {
    var keep = sorted[0];
    var remove = d.etfs.filter(function(e) { return e.code !== keep.code; });
    console.log('\n【' + d.key + '】保留：' + keep.code + ' ' + keep.name + ' (' + keep.size + '亿)');
    if (remove.length > 0) {
      console.log('  剔除：' + remove.map(function(e) { return e.code + '(' + (e.size || '无规模') + ')'; }).join(', '));
    }
  } else {
    console.log('\n【' + d.key + '】无规模数据，需人工判断');
    console.log('  候选：' + d.etfs.map(function(e) { return e.code + ' ' + e.name; }).join(', '));
  }
});
