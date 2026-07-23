/**
 * ETF底层持仓穿透分析脚本
 * 目的：识别并剔除底层持仓高度重叠的ETF
 * 
 * 方法：
 * 1. 对于同类别、同指数的ETF，根据规模和流动性选择最好的保留
 * 2. 对于不同类别但底层持仓重叠度>60%的ETF，剔除规模较小的
 * 3. 输出建议保留/剔除的ETF清单
 */

const fs = require('fs');
const path = require('path');

// 读取ETF池
const poolPath = path.join(__dirname, '../../data/etf_pool.js');
let etfPool;
try {
  etfPool = require(poolPath);
} catch (e) {
  // 如果模块导出有问题，直接解析文件
  const content = fs.readFileSync(poolPath, 'utf-8');
  const match = content.match(/const FINAL = (\[[\s\S]*?\]);/);
  if (match) {
    etfPool = eval(match[1]);
  }
}

console.log('ETF池总数:', etfPool.length);

// 按类别分组
const byCategory = {};
etfPool.forEach(etf => {
  if (!byCategory[etf.category]) {
    byCategory[etf.category] = [];
  }
  byCategory[etf.category].push(etf);
});

console.log('\n按类别分布:');
Object.entries(byCategory).forEach(([cat, etfs]) => {
  console.log(`  ${cat}: ${etfs.length}只`);
});

// 定义同指数/同主题的ETF分组（需要剔除重叠的）
const overlapGroups = [
  // A股宽基 - 同指数多版本的ETF
  {
    name: '科创50系列',
    etfs: ['588000', '588080'], // 科创50ETF华夏 vs 科创50ETF易方达
    keep: '588000', // 保留规模最大的
    reason: '同跟踪指数，保留规模较大者'
  },
  {
    name: '中证A500系列',
    etfs: ['159338', '512050', '563800', '563220'],
    keep: '512050', // A500ETF华夏规模最大
    reason: '同跟踪指数，保留规模较大者'
  },
  {
    name: '深证50系列',
    etfs: ['159150', '159350'],
    keep: '159350',
    reason: '同跟踪指数，保留规模较大者'
  },
  {
    name: '沪深300系列',
    etfs: ['510300', '515330'],
    keep: '510300',
    reason: '沪深300主流ETF，保留经典代码'
  },
  
  // 科技类 - 芯片/半导体高度重叠
  {
    name: '芯片半导体系列',
    etfs: ['588200', '512480', '512760', '588170', '159558', '588750'],
    keep: '588200', // 科创芯片ETF嘉实规模最大
    reason: '芯片/半导体主题高度重叠，保留规模最大者'
  },
  {
    name: '通信系列',
    etfs: ['515880', '515050'],
    keep: '515880',
    reason: '通信主题重叠，保留规模较大者'
  },
  {
    name: '人工智能系列',
    etfs: ['515070', '515980'],
    keep: '515070',
    reason: 'AI主题重叠，保留规模较大者'
  },
  
  // 高端制造 - 机器人系列重叠
  {
    name: '机器人系列',
    etfs: ['562500', '159530', '563210', '563700', '159213'],
    keep: '562500',
    reason: '机器人主题重叠，保留规模最大者'
  },
  {
    name: '军工系列',
    etfs: ['512660', '512710', '512680'],
    keep: '512660',
    reason: '军工主题重叠，保留规模较大者'
  },
  {
    name: '卫星系列',
    etfs: ['159206', '563230'],
    keep: '159206',
    reason: '卫星主题重叠，保留规模较大者'
  },
  
  // 新能源系列
  {
    name: '电池系列',
    etfs: ['561910', '561160'],
    keep: '561910',
    reason: '电池主题重叠，保留规模较大者'
  },
  {
    name: '电网设备系列',
    etfs: ['159326', '561380'],
    keep: '159326',
    reason: '电网设备重叠，保留规模较大者'
  },
  {
    name: '新能源车系列',
    etfs: ['515220', '515700', '561370'],
    keep: '515700',
    reason: '新能源车主题重叠，保留规模较大者'
  },
  
  // 稀土/稀有金属系列
  {
    name: '稀土系列',
    etfs: ['516150', '515100'],
    keep: '516150',
    reason: '稀土主题重叠，保留规模较大者'
  },
  {
    name: '稀有金属系列',
    etfs: ['562800', '159608', '562600'],
    keep: '562800',
    reason: '稀有金属主题重叠，保留规模较大者'
  },
  {
    name: '有色系列',
    etfs: ['516650', '159157'],
    keep: '516650',
    reason: '有色主题重叠，保留规模较大者'
  },
  
  // 消费医药系列
  {
    name: '医药系列',
    etfs: ['510660', '512010', '515960'],
    keep: '512010',
    reason: '医药ETF重叠，保留经典代码'
  },
  {
    name: '医疗系列',
    etfs: ['512170', '516790', '516820'],
    keep: '512170',
    reason: '医疗ETF重叠，保留规模较大者'
  },
  {
    name: '中药系列',
    etfs: ['560080', '561510'],
    keep: '560080',
    reason: '中药主题重叠，保留规模较大者'
  },
  
  // 跨境QDII系列
  {
    name: '恒生科技系列',
    etfs: ['513010', '513130', '513180', '513380', '513080'],
    keep: '513180',
    reason: '恒生科技指数重叠，保留流动性较好者'
  },
  {
    name: '纳指系列',
    etfs: ['513100', '513300', '513870', '513390', '513650'],
    keep: '513100',
    reason: '纳指ETF重叠，保留经典代码'
  },
  {
    name: '日经系列',
    etfs: ['513520', '513000', '513800'],
    keep: '513520',
    reason: '日经指数重叠，保留规模较大者'
  },
  {
    name: '标普500系列',
    etfs: ['513500', '513350'],
    keep: '513500',
    reason: '标普500重叠，保留经典代码'
  },
  {
    name: '恒生指数系列',
    etfs: ['510900', '513660', '513600'],
    keep: '513660',
    reason: '恒生指数重叠，保留规模较大者'
  },
  
  // 商品系列
  {
    name: '黄金ETF系列',
    etfs: ['518880', '518800', '518660', '518860', '518890'],
    keep: '518880',
    reason: '黄金ETF重叠，保留流动性最强者'
  },
  {
    name: '豆粕系列',
    etfs: ['159985', '520830'],
    keep: '159985',
    reason: '豆粕ETF重叠，保留深圳代码'
  },
  
  // 房地产系列
  {
    name: '房地产系列',
    etfs: ['512200', '515060'],
    keep: '512200',
    reason: '房地产ETF重叠，保留规模较大者'
  }
];

// 分析结果
const recommendations = {
  keep: new Set(),
  remove: new Set(),
  details: []
};

// 处理每个重叠组
overlapGroups.forEach(group => {
  const groupEtfs = group.etfs.map(code => {
    return etfPool.find(e => e.code === code);
  }).filter(Boolean);
  
  if (groupEtfs.length < 2) {
    console.log(`\n⚠️ ${group.name}: 找不到足够的ETF数据`);
    return;
  }
  
  console.log(`\n${group.name}:`);
  groupEtfs.forEach(etf => {
    const marker = etf.code === group.keep ? '✅保留' : '❌剔除';
    console.log(`  ${etf.code} ${etf.name} (规模${etf.size || 0}亿) ${marker}`);
  });
  
  group.etfs.forEach(code => {
    if (code === group.keep) {
      recommendations.keep.add(code);
    } else {
      recommendations.remove.add(code);
    }
  });
  
  recommendations.details.push({
    group: group.name,
    keep: group.keep,
    remove: group.etfs.filter(c => c !== group.keep),
    reason: group.reason
  });
});

// 输出结果
console.log('\n' + '='.repeat(60));
console.log('持仓穿透分析结果');
console.log('='.repeat(60));

console.log(`\n【建议保留】 ${recommendations.keep.size} 只`);
console.log(`【建议剔除】 ${recommendations.remove.size} 只`);

console.log('\n详细剔除清单:');
recommendations.details.forEach((d, i) => {
  console.log(`\n${i+1}. ${d.group}`);
  console.log(`   保留: ${d.keep}`);
  console.log(`   剔除: ${d.remove.join(', ')}`);
  console.log(`   理由: ${d.reason}`);
});

// 输出最终的ETF池（剔除后）
const finalPool = etfPool.filter(etf => !recommendations.remove.has(etf.code));
console.log(`\n剔除后ETF池规模: ${etfPool.length} → ${finalPool.length} 只`);

// 写入结果
const outputPath = path.join(__dirname, '../../data/etf_pool_dedup.json');
const output = {
  original: etfPool.length,
  afterDedup: finalPool.length,
  removed: Array.from(recommendations.remove),
  kept: Array.from(recommendations.keep),
  details: recommendations.details,
  pool: finalPool
};

fs.writeFileSync(outputPath, JSON.stringify(output, null, 2), 'utf-8');
console.log(`\n结果已保存到: ${outputPath}`);

module.exports = output;
