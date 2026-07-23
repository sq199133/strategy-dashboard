// Verify all candidate ETF codes against Sina data
const fs = require('fs');
const path = require('path');

const sina = JSON.parse(fs.readFileSync(path.join(__dirname,'sina_etf.json'),'utf8'));
const em = JSON.parse(fs.readFileSync(path.join(__dirname,'etf_all_raw.json'),'utf8'));
const emMap = {};
em.forEach(e => emMap[e.code] = e.size);

const targets = [
  {code:'159681', category:'创业板', note:'创业板50ETF?'},
  {code:'512770', category:'战略新兴', note:'原先误为生物医药'},
  {code:'512660', category:'军工', note:'军工ETF国泰'},
  {code:'512290', category:'生物医药', note:'生物医药ETF国泰'},
  {code:'515700', category:'新能源车', note:'新能源车ETF平安'},
  {code:'513100', category:'纳指', note:'纳指ETF国泰'},
  {code:'512100', category:'中证1000', note:'中证1000ETF南方'},
  {code:'588000', category:'科创50', note:'科创50ETF华夏'},
  {code:'512480', category:'半导体', note:'半导体ETF国联安'},
  {code:'512760', category:'芯片', note:'芯片ETF国泰'},
  {code:'562500', category:'机器人', note:'机器人ETF华夏'},
  {code:'515790', category:'光伏', note:'光伏ETF华泰'},
  {code:'512050', category:'A500', note:'A500ETF华夏'},
  {code:'510500', category:'中证500', note:'中证500ETF南方'},
  {code:'563800', category:'A500', note:'A500ETF广发'},
  {code:'563220', category:'A500', note:'A500ETF富国'},
  {code:'515880', category:'通信', note:'通信ETF国泰'},
  {code:'515050', category:'通信', note:'通信ETF华夏'},
  {code:'515070', category:'AI', note:'人工智能ETF华夏'},
  {code:'515980', category:'AI', note:'人工智能ETF华富'},
  {code:'588200', category:'科创芯片', note:'科创芯片ETF嘉实'},
  {code:'588170', category:'科创半导体', note:'科创半导体ETF华夏'},
  {code:'159326', category:'电网', note:'电网设备'},
  {code:'561910', category:'电池', note:'电池ETF招商'},
  {code:'516650', category:'有色', note:'有色金属ETF华夏'},
  {code:'516150', category:'稀土', note:'稀土ETF嘉实'},
  {code:'562800', category:'稀有金属', note:'稀有金属ETF嘉实'},
  {code:'510900', category:'恒生H股', note:'恒生中国企业ETF易方达'},
  {code:'513500', category:'标普500', note:'标普500ETF博时'},
  {code:'513520', category:'日经', note:'日经ETF华夏'},
  {code:'513030', category:'德国', note:'德国ETF华安'},
  {code:'513080', category:'法国', note:'法国ETF华安'},
  {code:'513000', category:'日经225', note:'日经225ETF易方达'},
  {code:'518880', category:'黄金', note:'黄金ETF华安'},
  {code:'518800', category:'黄金', note:'黄金ETF国泰'},
  {code:'515330', category:'沪深300', note:'沪深300ETF天弘'},
  {code:'588080', category:'科创50', note:'科创50ETF易方达'},
  {code:'159338', category:'中证A500', note:'中证A500'},
  {code:'512990', category:'MSCI', note:'MSCIA股ETF华夏'},
  {code:'513130', category:'恒生科技', note:'恒生科技ETF华泰柏瑞'},
  {code:'513050', category:'中概互联', note:'中概互联网ETF易方达'},
  {code:'513180', category:'恒生科技', note:'恒生科技ETF华夏'},
  {code:'513010', category:'恒生科技', note:'恒生科技ETF易方达'},
  {code:'513660', category:'恒生', note:'恒生ETF华夏'},
  {code:'513210', category:'恒生', note:'恒生ETF易方达'},
  {code:'513390', category:'纳指100', note:'纳指100ETF博时'},
  {code:'513110', category:'纳指', note:'纳指ETF华泰柏瑞'},
  {code:'513870', category:'纳指', note:'纳指ETF富国'},
  {code:'513300', category:'纳斯达克', note:'纳斯达克ETF华夏'},
  {code:'512180', category:'MSCI', note:'MSCIA股ETF建信'},
  {code:'512360', category:'MSCI', note:'MSCIA股ETF平安'},
  {code:'512520', category:'MSCI中国', note:'MSCI中国ETF华泰'},
  {code:'588220', category:'科创100', note:'科创100ETF鹏华'},
  {code:'159530', category:'机器人', note:'机器人E'},
  {code:'159206', category:'卫星', note:'卫星ETF'},
  {code:'512710', category:'军工', note:'军工龙头ETF富国'},
  {code:'512680', category:'军工', note:'军工ETF广发'},
  {code:'563230', category:'卫星', note:'卫星ETF富国'},
  {code:'159227', category:'航天航空', note:'航空航天'},
  {code:'561380', category:'电网', note:'电网设备ETF国泰'},
  {code:'159566', category:'储能', note:'储能电池'},
  {code:'516160', category:'新能源', note:'新能源ETF南方'},
  {code:'561160', category:'电池', note:'电池ETF富国'},
  {code:'515060', category:'房地产', note:'房地产ETF华夏'},
  {code:'512200', category:'房地产', note:'房地产ETF南方'},
  {code:'159253', category:'银行', note:'中证银行'},
  {code:'159260', category:'证券', note:'全指证券'},
  {code:'516620', category:'影视', note:'影视ETF国泰'},
  {code:'562700', category:'汽车零部件', note:'汽车零部件ETF华夏'},
  {code:'560080', category:'中药', note:'中药ETF汇添富'},
  {code:'561510', category:'中药', note:'中药ETF华泰柏瑞'},
  {code:'562390', category:'中药', note:'中药ETF银华'},
  {code:'512170', category:'医疗', note:'医疗ETF华宝'},
  {code:'512010', category:'医药', note:'医药ETF易方达'},
  {code:'510660', category:'医药', note:'医药ETF华夏'},
  {code:'512120', category:'医药', note:'医药ETF华安'},
  {code:'515960', category:'医药', note:'医药ETF嘉实'},
  {code:'515950', category:'医药50', note:'医药50ETF富国'},
  {code:'560260', category:'医疗', note:'医疗ETF广发'},
  {code:'516790', category:'医疗', note:'医疗ETF华泰柏瑞'},
  {code:'516820', category:'医疗创新', note:'医疗创新ETF平安'},
  {code:'516610', category:'医疗设备', note:'医疗设备ETF大成'},
  {code:'159562', category:'黄金股', note:'黄金股'},
  {code:'159321', category:'黄金产业', note:'黄金产业'},
  {code:'518860', category:'上海金', note:'上海金ETF建信'},
  {code:'518890', category:'上海金', note:'上海金ETF中银'},
  {code:'518660', category:'黄金', note:'黄金ETF工银'},
  {code:'513400', category:'道琼斯', note:'道琼斯ETF鹏华'},
  {code:'513850', category:'美国50', note:'美国50ETF易方达'},
  {code:'517080', category:'沪港深500', note:'沪港深500ETF汇添富'},
  {code:'515160', category:'MSCI中国', note:'MSCI中国ETF招商'},
  {code:'513600', category:'恒生指数', note:'恒生指数ETF南方'},
  {code:'513330', category:'恒生互联网', note:'恒生互联网ETF华夏'},
  {code:'513720', category:'港股互联网', note:'港股互联网ETF国泰'},
  {code:'513770', category:'港股互联网', note:'港股互联网ETF华宝'},
  {code:'513040', category:'港股通互联网', note:'港股通互联网ETF易方达'},
  {code:'513630', category:'港股低波', note:'港股低波红利ETF摩根'},
  {code:'513820', category:'港股通红利', note:'港股通红利ETF汇添富'},
  {code:'513950', category:'恒生红利', note:'恒生红利ETF富国'},
  {code:'513280', category:'恒生生物', note:'恒生生物科技ETF汇添富'},
  {code:'513060', category:'恒生医疗', note:'恒生医疗ETF博时'},
  {code:'513200', category:'港股通医药', note:'港股通医药ETF易方达'},
  {code:'513700', category:'港股通医药', note:'港股通医药ETF鹏华'},
  {code:'513930', category:'恒生生物', note:'恒生生物科技ETF华泰柏瑞'},
  {code:'513120', category:'港股创新药', note:'港股创新药ETF广发'},
  {code:'513780', category:'港股创新药', note:'港股创新药ETF景顺'},
  {code:'513980', category:'港股科技', note:'港股科技ETF景顺'},
  {code:'513020', category:'港股科技', note:'港股科技ETF国泰'},
  {code:'513160', category:'港股科技', note:'港股科技ETF银华'},
  {code:'513150', category:'港股通科技', note:'港股通科技ETF华泰柏瑞'},
  {code:'513550', category:'港股通50', note:'港股通50ETF华泰柏瑞'},
  {code:'513530', category:'港股通红利', note:'港股通红利ETF华泰柏瑞'},
  {code:'513690', category:'港股红利', note:'港股红利ETF博时'},
  {code:'513810', category:'港股国企', note:'港股国企ETF华夏'},
  {code:'513170', category:'恒生央企', note:'恒生央企ETF鹏华'},
  {code:'513990', category:'港股通', note:'港股通ETF招商'},
  {code:'515770', category:'MSCI中国A股', note:'MSCI中国A股ETF摩根'},
  {code:'513260', category:'恒生科技', note:'恒生科技ETF汇添富'},
  {code:'513380', category:'恒生科技', note:'恒生科技ETF广发'},
  {code:'513580', category:'恒生科技', note:'恒生科技ETF华安'},
  {code:'513890', category:'恒生科技', note:'恒生科技ETF摩根'},
  {code:'520500', category:'恒生创新药', note:'恒生创新药ETF华泰柏瑞'},
  {code:'520690', category:'港股创新药', note:'港股创新药ETF博时'},
  {code:'520760', category:'恒生生物', note:'恒生生物科技ETF摩根'},
  {code:'520930', category:'恒生生物', note:'恒生生物科技ETF国泰'},
  {code:'520880', category:'港股通创新药', note:'港股通创新药ETF华宝'},
  {code:'520970', category:'港股通创新药', note:'港股通创新药ETF嘉实'},
  {code:'520700', category:'港股通创新药', note:'港股通创新药ETF万家'},
  {code:'520550', category:'港股红利低波', note:'港股红利低波ETF招商'},
  {code:'520630', category:'港股通互联网', note:'港股通互联网ETF广发'},
  {code:'520650', category:'港股通互联网', note:'港股通互联网ETF南方'},
  {code:'520910', category:'港股通互联网', note:'港股通互联网ETF华夏'},
  {code:'520810', category:'港股通红利', note:'港股通红利ETF易方达'},
  {code:'520900', category:'港股通红利', note:'港股通红利ETF广发'},
  {code:'520590', category:'恒生科技', note:'恒生科技ETF鹏华'},
  {code:'520530', category:'港股通科技', note:'港股通科技ETF东财'},
  {code:'520920', category:'恒生科技', note:'恒生科技ETF天弘'},
  {code:'159105', category:'港股', note:'恒生生科'},
  {code:'159109', category:'港股', note:'恒生50'},
  {code:'159131', category:'港股', note:'港股信息'},
  {code:'159143', category:'港股', note:'港股央企'},
  {code:'159277', category:'港股', note:'港股高息'},
  {code:'159280', category:'港股', note:'HK互联网'},
  {code:'159286', category:'港股', note:'港股新药'},
  {code:'159607', category:'港股', note:'中概互联'},
  {code:'159605', category:'港股', note:'互联中概'},
  {code:'159568', category:'港股', note:'港股互联'},
  {code:'159545', category:'港股', note:'港股红利'},
  {code:'159519', category:'港股', note:'港股国企'},
  {code:'159561', category:'港股', note:'德国ETF'},
  {code:'159577', category:'港股', note:'美国50'},
  {code:'159612', category:'港股', note:'国泰标普'},
  {code:'159501', category:'港股', note:'纳指基金'},
  {code:'159502', category:'港股', note:'标普生科'},
  {code:'159509', category:'港股', note:'纳指科技'},
  {code:'159513', category:'港股', note:'纳指大成'},
  {code:'159518', category:'港股', note:'标普油气'},
  {code:'159550', category:'港股', note:'互联网AH'},
  {code:'159318', category:'港股', note:'港股通基'},
  {code:'159331', category:'港股', note:'红利港股'},
];

// Search by partial name
const searchTerms = [
  '创业板50','纳指100','中证A50','标普油气','豆粕',
  '纳斯达克','港股100','恒生科技','中概互联','港股通'
];
searchTerms.forEach(term => {
  const results = sina.filter(e => e.name.includes(term));
  if (results.length > 0) {
    results.slice(0,5).forEach(e => {
      const s = emMap[e.code]||0;
      console.log('TERM['+term+'] => '+e.code+' '+e.name+' '+(s>0?s.toFixed(1)+'亿':'?亿'));
    });
  } else {
    console.log('TERM['+term+'] => ❌ 未找到');
  }
});

// Now check all targets
let found = [], notFound = [];
targets.forEach(t => {
  const f = sina.find(e => e.code === t.code);
  if (f) {
    found.push({code:t.code, sinaName:f.name, note:t.note, cat:t.category, size:emMap[t.code]||0});
  } else {
    notFound.push(t);
  }
});

found.sort((a,b)=>a.code-b.code);
console.log('\n===== 已验证 ('+found.length+') =====');
found.forEach(e => {
  const s = e.size>0?e.size.toFixed(1)+'亿':'?亿';
  console.log(e.code+' | '+e.sinaName+' | '+s+' | '+e.cat+' | '+e.note);
});

console.log('\n===== 未找到 ('+notFound.length+') =====');
notFound.forEach(t => console.log(t.code+' | '+t.note));
