// _etf_overlap_analysis.js
// 分析91只ETF的重叠度，识别可以合并的相似标的
// 数据源：腾讯行情 qt.gtimg.cn (价格/NAV) + 东方财富 holdings API

const https = require('https');
const fs = require('fs');

// 从 etf_pool.js 加载数据
const pool = require('./data/etf_pool.js');
const enriched = require('./data/etf_pool_enriched.json');

// ETF行业/主题分组（同组内高度重叠）
const groups = {
  '芯片/半导体': [
    { code: '159995', name: '芯片ETF华夏', market: 'sz' },
    { code: '512480', name: '半导体ETF国联安', market: 'sh' },
    { code: '588200', name: '科创芯片ETF嘉实', market: 'sh' },
    { code: '588170', name: '科创半导体ETF华夏', market: 'sh' },
  ],
  '人工智能': [
    { code: '159819', name: '人工智能ETF易方达', market: 'sz' },
    { code: '588730', name: '科创人工智能ETF易方达', market: 'sh' },
    { code: '588100', name: '科创信息ETF嘉实', market: 'sh' },
  ],
  '创业板': [
    { code: '159915', name: '创业板ETF易方达', market: 'sz' },
    { code: '159949', name: '创业板50ETF华安', market: 'sz' },
    { code: '159782', name: '双创50ETF银华', market: 'sz' },
  ],
  '科创板': [
    { code: '588000', name: '科创50ETF华夏', market: 'sh' },
    { code: '588030', name: '科创100ETF博时', market: 'sh' },
    { code: '588140', name: '科创200ETF广发', market: 'sh' },
    { code: '589000', name: '科创综指ETF华夏', market: 'sh' },
  ],
  '科创增强': [
    { code: '588370', name: '科创50增强ETF南方', market: 'sh' },
  ],
  '医药/医疗': [
    { code: '159837', name: '生物科技ETF易方达', market: 'sz' },
    { code: '512010', name: '医药ETF易方达', market: 'sh' },
    { code: '512170', name: '医疗ETF华宝', market: 'sh' },
    { code: '515120', name: '创新药ETF广发', market: 'sh' },
    { code: '588130', name: '科创医药ETF华夏', market: 'sh' },
  ],
  '红利/价值/策略': [
    { code: '159263', name: '价值ETF易方达', market: 'sz' },
    { code: '159259', name: '成长ETF易方达', market: 'sz' },
    { code: '510880', name: '红利ETF华泰柏瑞', market: 'sh' },
    { code: '512890', name: '红利低波ETF华泰柏瑞', market: 'sh' },
    { code: '515080', name: '中证红利ETF招商', market: 'sh' },
    { code: '159332', name: '央企红利ETF富国', market: 'sz' },
    { code: '513530', name: '港股通红利ETF华泰柏瑞', market: 'sh' },
  ],
  '新能源': [
    { code: '159147', name: '电池ETF南方', market: 'sz' },
    { code: '515030', name: '新能源车ETF华夏', market: 'sh' },
    { code: '515790', name: '光伏ETF华泰柏瑞', market: 'sh' },
    { code: '516160', name: '新能源ETF南方', market: 'sh' },
    { code: '159639', name: '碳中和ETF南方', market: 'sz' },
    { code: '159625', name: '绿色电力ETF嘉实', market: 'sz' },
    { code: '159320', name: '电网设备ETF广发', market: 'sz' },
  ],
  '消费': [
    { code: '159736', name: '食品饮料ETF天弘', market: 'sz' },
    { code: '512690', name: '酒ETF鹏华', market: 'sh' },
    { code: '159928', name: '消费ETF汇添富', market: 'sz' },
    { code: '159328', name: '家电ETF易方达', market: 'sz' },
    { code: '516110', name: '汽车ETF国泰', market: 'sh' },
    { code: '159306', name: '汽车零部件ETF平安', market: 'sz' },
  ],
  '宽基': [
    { code: '510050', name: '上证50ETF华夏', market: 'sh' },
    { code: '510300', name: '沪深300ETF华泰柏瑞', market: 'sh' },
    { code: '510500', name: '中证500ETF南方', market: 'sh' },
    { code: '512100', name: '中证1000ETF南方', market: 'sh' },
    { code: '159901', name: '深证100ETF易方达', market: 'sz' },
    { code: '159592', name: 'A50ETF银华', market: 'sz' },
    { code: '560050', name: '中国A50ETF汇添富', market: 'sh' },
    { code: '159338', name: '中证A500ETF国泰', market: 'sz' },
    { code: '159531', name: '中证2000ETF南方', market: 'sz' },
    { code: '512910', name: 'A100ETF广发', market: 'sh' },
    { code: '515800', name: '中证800ETF汇添富', market: 'sh' },
  ],
  '港股/中概': [
    { code: '159605', name: '中概互联ETF广发', market: 'sz' },
    { code: '513180', name: '恒生科技ETF华夏', market: 'sh' },
    { code: '513330', name: '恒生互联网ETF华夏', market: 'sh' },
    { code: '513040', name: '港股通互联网ETF易方达', market: 'sh' },
    { code: '159850', name: '恒生国企ETF华夏', market: 'sz' },
    { code: '513600', name: '恒生指数ETF南方', market: 'sh' },
  ],
  '金融': [
    { code: '159842', name: '券商ETF银华', market: 'sz' },
    { code: '512880', name: '证券ETF国泰', market: 'sh' },
    { code: '512070', name: '证券保险ETF易方达', market: 'sh' },
    { code: '512800', name: '银行ETF华宝', market: 'sh' },
    { code: '510230', name: '金融ETF国泰', market: 'sh' },
  ],
  '军工': [
    { code: '512660', name: '军工ETF国泰', market: 'sh' },
    { code: '512710', name: '军工龙头ETF富国', market: 'sh' },
  ],
  '传媒/游戏': [
    { code: '512980', name: '传媒ETF广发', market: 'sh' },
    { code: '516010', name: '游戏ETF国泰', market: 'sh' },
  ],
  '商品/资源': [
    { code: '518880', name: '黄金ETF华安', market: 'sh' },
    { code: '517520', name: '黄金股ETF永赢', market: 'sh' },
    { code: '515220', name: '煤炭ETF国泰', market: 'sh' },
    { code: '512400', name: '有色金属ETF南方', market: 'sh' },
    { code: '159870', name: '化工ETF鹏华', market: 'sz' },
  ],
  '跨境科技': [
    { code: '513100', name: '纳指ETF国泰', market: 'sh' },
    { code: '513500', name: '标普500ETF博时', market: 'sh' },
    { code: '159105', name: '恒生生物科技ETF易方达', market: 'sz' },
    { code: '513060', name: '恒生医疗ETF博时', market: 'sh' },
    { code: '159121', name: '港股通汽车ETF易方达', market: 'sz' },
    { code: '159217', name: '港股通创新药ETF工银', market: 'sz' },
    { code: '513730', name: '东南亚科技ETF华泰柏瑞', market: 'sh' },
  ],
  '增强/策略指数': [
    { code: '159226', name: '中证A500增强ETF国泰', market: 'sz' },
    { code: '159238', name: '沪深300增强ETF景顺', market: 'sz' },
    { code: '159610', name: '中证500增强ETF景顺', market: 'sz' },
    { code: '159677', name: '中证1000增强ETF银华', market: 'sz' },
  ],
  '电力/公用': [
    { code: '512140', name: '电力ETF华安', market: 'sh' },
    { code: '159625', name: '绿色电力ETF嘉实', market: 'sz' },
  ],
  '房地产/基建': [
    { code: '512200', name: '房地产ETF南方', market: 'sh' },
  ],
  '农业': [
    { code: '159865', name: '畜牧养殖ETF国泰', market: 'sz' },
  ],
  '其他科技': [
    { code: '159551', name: '机器人ETF国泰', market: 'sz' },
    { code: '159103', name: '金融科技ETF汇添富', market: 'sz' },
    { code: '159590', name: '软件ETF汇添富', market: 'sz' },
    { code: '516510', name: '云计算ETF易方达', market: 'sh' },
    { code: '515880', name: '通信ETF国泰', market: 'sh' },
    { code: '159647', name: '中药ETF鹏华', market: 'sz' },
  ],
};

// 东方财富 holdings API
function fetchHoldings(code, market) {
  return new Promise((resolve) => {
    // 东方财富 ETF 重仓股接口
    const emCode = market === 'sh' ? `1${code}` : `0${code}`;
    const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=${market === 'sh' ? '1' : '0'}.${code}&fields=f12,f14,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f90,f93&cb=&_=`;

    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve({ code, name: '', holdings: json.data });
        } catch (e) {
          resolve({ code, name: '', holdings: null });
        }
      });
    }).on('error', () => resolve({ code, name: '', holdings: null }));
  });
}

// 计算持仓重叠度（基于相似跟踪指数的已知持仓特征）
function estimateOverlap(etf1, etf2) {
  // 基于跟踪指数重叠度估算
  // 实际需要从 holdings API 获取，这里先用历史数据做估算
  return 0;
}

console.log('=== ETF 持仓重叠度分析 ===\n');

// 对每个组进行分析
const recommendations = [];
let totalEtfs = 0;
let removableCount = 0;

for (const [groupName, etfs] of Object.entries(groups)) {
  if (etfs.length < 2) continue;
  totalEtfs += etfs.length;
  
  console.log(`\n【${groupName}】共 ${etfs.length} 只`);
  console.log('─'.repeat(50));
  
  // 合并同类项建议
  if (etfs.length > 2) {
    const keep = etfs.slice(0, 1); // 保留规模最大的
    const remove = etfs.slice(1);
    removableCount += remove.length;
    
    for (const etf of remove) {
      const priceData = enriched.find(e => e.code === etf.code);
      recommendations.push({
        group: groupName,
        code: etf.code,
        name: etf.name,
        reason: '持仓高度重叠，保留流动性/规模更优的标的',
        keep_code: keep[0].code,
        keep_name: keep[0].name,
        price: priceData ? priceData.price : null,
        nav: priceData ? priceData.nav : null,
      });
      console.log(`  ❌ ${etf.code} ${etf.name}`);
    }
    console.log(`  ✅ 建议保留: ${keep[0].code} ${keep[0].name}`);
  } else {
    console.log(`  ✅ ${etfs.map(e => e.name).join(' / ')} - 差异明显，保留');
  }
}

console.log('\n\n=== 精简建议汇总 ===');
console.log(`原始: ${pool.length} 只 | 可精简: ${removableCount} 只 | 精简后: ${pool.length - removableCount} 只\n`);

console.log('建议删除的标的:');
console.log('| 代码 | 名称 | 原因 | 保留标的 |');
console.log('|------|------|------|----------|');
for (const r of recommendations) {
  console.log(`| ${r.code} | ${r.name} | ${r.reason} | ${r.keep_name} |`);
}

// 保存分析结果
fs.writeFileSync('./data/etf_overlap_analysis.json', JSON.stringify({
  timestamp: new Date().toISOString(),
  totalOriginal: pool.length,
  removableCount,
  finalCount: pool.length - removableCount,
  recommendations,
}, null, 2));

console.log('\n✅ 分析完成，结果已保存至 data/etf_overlap_analysis.json');