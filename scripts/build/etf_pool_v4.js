/**
 * ETF标的池 v4.0 — 最终版（2026-04-17核实定稿）
 * 数据来源：新浪财经实时行情 + 东方财富规模数据
 * 核实方式：逐行代码对比新浪/东财API确认
 * 
 * 分类体系：
 *   A股宽基 · 科技 · 高端制造 · 新能源 · 消费医药
 *   金融地产 · 周期资源 · 策略指数 · 跨境QDII · 商品
 */

const POOL = [
  // ═══════════════════════════════════════════════════
  // A股宽基 (15只)
  // ═══════════════════════════════════════════════════
  { code:'510500', name:'中证500ETF南方',        market:'SH', category:'A股宽基', size:820.5 },
  { code:'588000', name:'科创50ETF华夏',          market:'SH', category:'A股宽基', size:720.1 },
  { code:'588080', name:'科创50ETF易方达',        market:'SH', category:'A股宽基', size:398.1 },
  { code:'159338', name:'中证A500',               market:'SZ', category:'A股宽基', size:290.8 },
  { code:'512050', name:'A500ETF华夏',            market:'SH', category:'A股宽基', size:258.3 },
  { code:'512100', name:'中证1000ETF南方',         market:'SH', category:'A股宽基', size:250.6 },
  { code:'563800', name:'A500ETF广发',            market:'SH', category:'A股宽基', size:119.0 },
  { code:'563220', name:'A500ETF富国',            market:'SH', category:'A股宽基', size: 92.5 },
  { code:'588220', name:'科创100ETF鹏华',         market:'SH', category:'A股宽基', size: 90.7 },
  { code:'515330', name:'沪深300ETF天弘',          market:'SH', category:'A股宽基', size: 88.5 },
  { code:'159591', name:'中证A50',                market:'SZ', category:'A股宽基', size:  0   },
  { code:'159602', name:'中国A50',                market:'SZ', category:'A股宽基', size:  0   },
  { code:'159531', name:'中证2000',               market:'SZ', category:'A股宽基', size:  8.9 },
  { code:'159150', name:'深证50E',                market:'SZ', category:'A股宽基', size:  1.5 },
  { code:'159350', name:'深证50',                 market:'SZ', category:'A股宽基', size:  1.7 },

  // ═══════════════════════════════════════════════════
  // 科技 (13只)
  // ═══════════════════════════════════════════════════
  { code:'588200', name:'科创芯片ETF嘉实',        market:'SH', category:'科技', size:407.2 },
  { code:'512480', name:'半导体ETF国联安',        market:'SH', category:'科技', size:204.6 },
  { code:'515880', name:'通信ETF国泰',            market:'SH', category:'科技', size:181.6 },
  { code:'515070', name:'人工智能ETF华夏',        market:'SH', category:'科技', size:104.4 },
  { code:'515050', name:'通信ETF华夏',            market:'SH', category:'科技', size: 97.4 },
  { code:'512760', name:'芯片ETF国泰',            market:'SH', category:'科技', size: 96.0 },
  { code:'515980', name:'人工智能ETF华富',        market:'SH', category:'科技', size: 89.7 },
  { code:'588170', name:'科创半导体ETF华夏',      market:'SH', category:'科技', size: 83.3 },
  { code:'159558', name:'半导体E',               market:'SZ', category:'科技', size: 53.8 },
  { code:'588750', name:'科创芯片ETF汇添富',      market:'SH', category:'科技', size: 49.0 },
  { code:'159539', name:'信创50',                market:'SZ', category:'科技', size:  0   },
  { code:'159541', name:'创业板综',               market:'SZ', category:'科技', size:  1.3 },
  { code:'159213', name:'机器人TF',              market:'SZ', category:'科技', size:  6.5 },

  // ═══════════════════════════════════════════════════
  // 高端制造 (8只)
  // ═══════════════════════════════════════════════════
  { code:'562500', name:'机器人ETF华夏',          market:'SH', category:'高端制造', size:218.1 },
  { code:'159206', name:'卫星ETF',                market:'SZ', category:'高端制造', size:211.8 },
  { code:'159530', name:'机器人E',               market:'SZ', category:'高端制造', size:146.9 },
  { code:'512660', name:'军工ETF国泰',            market:'SH', category:'高端制造', size:102.8 },
  { code:'512710', name:'军工龙头ETF富国',        market:'SH', category:'高端制造', size: 98.1 },
  { code:'512680', name:'军工ETF广发',            market:'SH', category:'高端制造', size: 55.5 },
  { code:'563230', name:'卫星ETF富国',            market:'SH', category:'高端制造', size: 47.7 },
  { code:'159227', name:'航空航天',               market:'SZ', category:'高端制造', size: 43.9 },

  // ═══════════════════════════════════════════════════
  // 新能源 (9只)
  // ═══════════════════════════════════════════════════
  { code:'159326', name:'电网设备',               market:'SZ', category:'新能源', size:319.1 },
  { code:'515790', name:'光伏ETF华泰柏瑞',        market:'SH', category:'新能源', size:100.5 },
  { code:'159566', name:'储能电池',               market:'SZ', category:'新能源', size: 79.8 },
  { code:'516160', name:'新能源ETF南方',          market:'SH', category:'新能源', size: 79.3 },
  { code:'561380', name:'电网设备ETF国泰',        market:'SH', category:'新能源', size: 62.8 },
  { code:'561910', name:'电池ETF招商',            market:'SH', category:'新能源', size: 44.1 },
  { code:'561160', name:'电池ETF富国',            market:'SH', category:'新能源', size: 20.1 },
  { code:'515700', name:'新能源车ETF平安',        market:'SH', category:'新能源', size: 18.7 },
  { code:'159187', name:'景顺新能',               market:'SZ', category:'新能源', size:  1.1 },

  // ═══════════════════════════════════════════════════
  // 消费医药 (9只)
  // ═══════════════════════════════════════════════════
  { code:'510660', name:'医药ETF华夏',            market:'SH', category:'消费医药', size:  0   },
  { code:'512010', name:'医药ETF易方达',          market:'SH', category:'消费医药', size:  0   },
  { code:'512170', name:'医疗ETF华宝',            market:'SH', category:'消费医药', size:  0   },
  { code:'512290', name:'生物医药ETF国泰',        market:'SH', category:'消费医药', size:  0   },
  { code:'515960', name:'医药ETF嘉实',            market:'SH', category:'消费医药', size:  0   },
  { code:'516790', name:'医疗ETF华泰柏瑞',        market:'SH', category:'消费医药', size:  0   },
  { code:'516820', name:'医疗创新ETF平安',        market:'SH', category:'消费医药', size:  0   },
  { code:'560080', name:'中药ETF汇添富',          market:'SH', category:'消费医药', size:  0   },
  { code:'561510', name:'中药ETF华泰柏瑞',        market:'SH', category:'消费医药', size:  0   },

  // ═══════════════════════════════════════════════════
  // 金融地产 (4只)
  // ═══════════════════════════════════════════════════
  { code:'159253', name:'中证银行',               market:'SZ', category:'金融地产', size:  0   },
  { code:'159260', name:'全指证券',               market:'SZ', category:'金融地产', size:  0   },
  { code:'512200', name:'房地产ETF南方',           market:'SH', category:'金融地产', size: 52.7 },
  { code:'515060', name:'房地产ETF华夏',           market:'SH', category:'金融地产', size:  6.5 },

  // ═══════════════════════════════════════════════════
  // 周期资源 (6只)
  // ═══════════════════════════════════════════════════
  { code:'516650', name:'有色金属ETF华夏',        market:'SH', category:'周期资源', size:140.9 },
  { code:'516150', name:'稀土ETF嘉实',            market:'SH', category:'周期资源', size: 93.5 },
  { code:'562800', name:'稀有金属ETF嘉实',        market:'SH', category:'周期资源', size: 78.1 },
  { code:'159608', name:'稀有金属',               market:'SZ', category:'周期资源', size: 55.4 },
  { code:'159157', name:'有色TH',                 market:'SZ', category:'周期资源', size: 67.0 },
  { code:'510170', name:'大宗商品ETF国联安',      market:'SH', category:'周期资源', size:  0   },

  // ═══════════════════════════════════════════════════
  // 策略指数 (6只)
  // ═══════════════════════════════════════════════════
  { code:'515900', name:'央企创新ETF博时',        market:'SH', category:'策略指数', size: 39.2 },
  { code:'159259', name:'成长ETF',                market:'SZ', category:'策略指数', size: 16.5 },
  { code:'588020', name:'科创成长ETF易方达',      market:'SH', category:'策略指数', size: 10.5 },
  { code:'159525', name:'红利低波',               market:'SZ', category:'策略指数', size:  0   },
  { code:'159117', name:'标普红利',               market:'SZ', category:'策略指数', size:  0   },
  { code:'159332', name:'央企红利',               market:'SZ', category:'策略指数', size:  0   },

  // ═══════════════════════════════════════════════════
  // 跨境QDII (22只)
  // ═══════════════════════════════════════════════════
  { code:'510900', name:'恒生中国企业ETF易方达',  market:'SH', category:'跨境QDII', size:  0   },
  { code:'513660', name:'恒生ETF华夏',            market:'SH', category:'跨境QDII', size:  0   },
  { code:'513600', name:'恒生指数ETF南方',        market:'SH', category:'跨境QDII', size:  0   },
  { code:'513010', name:'恒生科技ETF易方达',      market:'SH', category:'跨境QDII', size:  0   },
  { code:'513130', name:'恒生科技ETF华泰柏瑞',    market:'SH', category:'跨境QDII', size:  0   },
  { code:'513180', name:'恒生科技ETF华夏',        market:'SH', category:'跨境QDII', size:  0   },
  { code:'513380', name:'恒生科技ETF广发',        market:'SH', category:'跨境QDII', size:  0   },
  { code:'513050', name:'中概互联网ETF易方达',    market:'SH', category:'跨境QDII', size:  0   },
  { code:'513330', name:'恒生互联网ETF华夏',      market:'SH', category:'跨境QDII', size:  0   },
  { code:'513720', name:'港股互联网ETF国泰',      market:'SH', category:'跨境QDII', size:  0   },
  { code:'513060', name:'恒生医疗ETF博时',        market:'SH', category:'跨境QDII', size:  0   },
  { code:'513120', name:'港股创新药ETF广发',      market:'SH', category:'跨境QDII', size:  0   },
  { code:'513500', name:'标普500ETF博时',         market:'SH', category:'跨境QDII', size:  0   },
  { code:'513390', name:'纳指100ETF博时',         market:'SH', category:'跨境QDII', size:  0   },
  { code:'513100', name:'纳指ETF国泰',            market:'SH', category:'跨境QDII', size:  0   },
  { code:'513300', name:'纳斯达克ETF华夏',        market:'SH', category:'跨境QDII', size:  0   },
  { code:'513870', name:'纳指ETF富国',            market:'SH', category:'跨境QDII', size:  0   },
  { code:'513520', name:'日经ETF华夏',            market:'SH', category:'跨境QDII', size:  0   },
  { code:'513000', name:'日经225ETF易方达',       market:'SH', category:'跨境QDII', size:  0   },
  { code:'513030', name:'德国ETF华安',            market:'SH', category:'跨境QDII', size:  0   },
  { code:'513400', name:'道琼斯ETF鹏华',          market:'SH', category:'跨境QDII', size:  0   },
  { code:'513850', name:'美国50ETF易方达',        market:'SH', category:'跨境QDII', size:  0   },

  // ═══════════════════════════════════════════════════
  // 商品 (6只)
  // ═══════════════════════════════════════════════════
  { code:'518880', name:'黄金ETF华安',             market:'SH', category:'商品', size:  0   },
  { code:'518800', name:'黄金ETF国泰',             market:'SH', category:'商品', size:  0   },
  { code:'518660', name:'黄金ETF工银',             market:'SH', category:'商品', size:  0   },
  { code:'518860', name:'上海金ETF建信',           market:'SH', category:'商品', size:  0   },
  { code:'518890', name:'上海金ETF中银',           market:'SH', category:'商品', size:  0   },
  { code:'159562', name:'黄金股',                  market:'SZ', category:'商品', size:  0   },
];

module.exports = POOL;

// 输出统计摘要
const cats = {};
POOL.forEach(e => { cats[e.category] = (cats[e.category]||0)+1; });
console.log('ETF池 v4.0 总计:', POOL.length, '只');
Object.entries(cats).forEach(([cat,cnt]) => console.log('  '+cat+':',cnt+'只'));
