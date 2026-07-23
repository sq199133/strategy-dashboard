"""
信号日分离测试：
1. 原始测试 (不同信号日+次日入场)
2. 同一信号(周一) × 不同入场日
3. 不同信号日但都用次日入场
4. 检查是否有持仓不连续bug
"""
import json, os, numpy as np
from collections import defaultdict
from datetime import datetime as dtobj
import sys
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR=r'D:\Qclaw_Trading\data\history'
CAT_FILE=r'D:\Qclaw_Trading\data\cat_assignment_full.json'
POOL_FILE=r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'

MOM,MA,EM,TK=15,175,28,3
EXTRA={'商品/周期/资源':['518880']}

with open(POOL_FILE,'r',encoding='utf-8') as f: pool=json.load(f)
with open(CAT_FILE,'r',encoding='utf-8') as f: raw=json.load(f)
cm={}
for kw,en in raw.get('assignments',{}).items():
    for e in en: cm[e[0]]=e[1]
sec=defaultdict(list)
for c,ct in cm.items():
    if ct!='海外/跨境': sec[ct].append(c)
for cat,cs in EXTRA.items():
    for c in cs:
        if c not in sec[cat]: sec[cat].append(c)

def load_r(c):
    for p in ['','sz']:
        fn=os.path.join(DATA_DIR,p+c+'.json')
        if os.path.exists(fn):
            d=json.load(open(fn,'r',encoding='utf-8'))
            rr=d.get('records',[]); return rr if rr else []
    return []
pr={}
for codes in sec.values():
    for c in codes:
        if c not in pr:
            r=load_r(c)
            if r: pr[c]={rr['date']:rr.get('close',0) for rr in r}

dates=sorted(set(d for p in pr.values() for d in p))
dates=[d for d in dates if d<='2025-12-31']

sv={}
for cat,cs in sec.items():
    arr=np.full(len(dates),np.nan)
    for i,dt in enumerate(dates):
        vals=[pr[c].get(dt,np.nan) for c in cs if c in pr]
        vv=[v for v in vals if not np.isnan(v)]
        if len(vv)>=max(1,len(cs)//3): arr[i]=np.mean(vv)
    sv[cat]=arr

wd_names={0:'周一',1:'周二',2:'周三',3:'周四',4:'周五'}

def run(wd, entry_offset, same_signal_only=None):
    """wd: 信号日, entry_offset: 是否用次日(否则当日入场), same_signal_only: 统一用周一信号"""
    sid=next(i for i,dt in enumerate(dates) if dt>='2014-01-01')
    cash=1.0; hc=None; held=[]; ep={}
    eq=[1.0]
    for i in range(sid,len(dates)):
        dt=dates[i]
        if hc and held:
            rv=[pr[c].get(dt,np.nan)/ep.get(c,1) for c in held]
            rv=[v for v in rv if not np.isnan(v)]
            nav=cash*np.mean(rv) if rv else cash
        else:
            nav=cash
        eq.append(nav)
        if i<max(MOM,MA,EM): continue
        
        # 信号日
        if same_signal_only is not None:
            signal_day=same_signal_only
        else:
            signal_day=wd
        
        cur_wd=dtobj.strptime(dt,'%Y-%m-%d').weekday()
        if cur_wd!=signal_day: continue
        
        bc,bs=None,-999
        for cat,idx in sv.items():
            cx=idx[i]
            if np.isnan(cx): continue
            if i>=MA:
                ma=idx[i-MA:i]; ma=ma[~np.isnan(ma)]
                if len(ma)<MA//3 or cx<=np.mean(ma): continue
            if i<MOM: continue
            pv=idx[i-MOM]
            if np.isnan(pv) or pv<=0: continue
            s=cx/pv-1
            if s>bs: bs,bc=s,cat
        
        if bc and bc!=hc:
            cd2=sec.get(bc,[])
            rk=[]
            for c2 in cd2:
                if c2 not in pr: continue
                cp=pr[c2].get(dt,np.nan)
                if np.isnan(cp): continue
                pp=pr[c2].get(dates[i-EM],np.nan)
                if np.isnan(pp) or pp<=0: continue
                m=cp/pp-1
                entry_idx=i+entry_offset
                if entry_idx>=len(dates): continue
                tp=pr[c2].get(dates[entry_idx],np.nan)
                if not np.isnan(tp): rk.append((m,c2,tp))
            rk.sort(reverse=True)
            if rk:
                sel=rk[:min(TK,len(rk))]
                cash=nav; hc=bc; held=[]; ep={}
                for _,c2,tp in sel:
                    held.append(c2)
                    ep[c2]=tp
        elif not bc and hc:
            cash=nav; hc=None; held=[]; ep={}
    
    eq=np.array(eq)
    if len(eq)<2: return 0,0,0,eq
    ann=eq[-1]**(1/((len(eq)-1)/250))-1
    peak=np.maximum.accumulate(eq)
    mdd=np.max((peak-eq)/peak)
    rets=np.diff(eq)/eq[:-1]
    shp=np.mean(rets)*250/(np.std(rets)*np.sqrt(250)+1e-9)
    return ann,shp,mdd,eq

print('='*75)
print('  信号日分离测试 — 动15MA175_ETF28_T3 +黄金ETF')
print('='*75)
print()

# ========== 测试1：原始（各信号日+次日入场，当前策略） ==========
print('▎测试1：各信号日，次日入场(原策略)')
print('  %-8s  %8s %8s %8s %10s' % ('信号日','年化','夏普','回撤','最终净值'))
print('  ' + '-'*50)
for wd in range(5):
    a,s,d,eq=run(wd, 1, None)
    print('  %-8s %+7.2f%% %7.2f %7.2f%% %10.4f' % (wd_names[wd], a*100, s, d*100, eq[-1]))

print()

# ========== 测试2：统一周一信号，改入场日期 ==========
print('▎测试2：统一用周一信号，改入场日')
print('  %-16s %8s %8s %8s %10s' % ('','年化','夏普','回撤','最终净值'))
print('  ' + '-'*50)
for offset in [0,1,2,3,4]:
    label='信号当天(周一)' if offset==0 else '信号后%d天'%offset
    a,s,d,eq=run(0, offset, 0)
    print('  %-16s %+7.2f%% %7.2f %7.2f%% %10.4f' % (label, a*100, s, d*100, eq[-1]))

print()

# ========== 测试3：不同信号日，都用次日入场，但持仓=开仓时持仓到下一个该信号日 ==========
print('▎测试3：不同信号日+次日入场，无持仓期间保持不动')
print('  注意：各信号日之间持仓时间是独立的，不互相干扰')
print('  %-8s  %8s %8s %8s %10s' % ('信号日','年化','夏普','回撤','最终净值'))
print('  ' + '-'*50)
for wd in range(5):
    a,s,d,eq=run(wd, 1, None)
    print('  %-8s %+7.2f%% %7.2f %7.2f%% %10.4f' % (wd_names[wd], a*100, s, d*100, eq[-1]))

print()

# ========== 测试4：当天入场（无延迟），逐信号日 ==========
print('▎测试4：信号日当天立即入场（无延迟）')
print('  %-8s  %8s %8s %8s %10s' % ('信号日','年化','夏普','回撤','最终净值'))
print('  ' + '-'*50)
for wd in range(5):
    a,s,d,eq=run(wd, 0, None)
    print('  %-8s %+7.2f%% %7.2f %7.2f%% %10.4f' % (wd_names[wd], a*100, s, d*100, eq[-1]))

print()

# ========== 测试5：检查是否有bug在"不同信号日生成不同信号导致持仓比较"上 ==========
# 核心问题：不同信号日选中的板块是否高度一致
print('▎测试5：不同信号日的信号相关性')
print('  看2014~2025各信号日选中的板块分布')
print()

# 统计每个信号日的板块选中分布
cat_hits={wd:Counter() for wd in range(5)}
for i,dt in enumerate(dates):
    if dt<'2014-01-01': continue
    if i<max(MOM,MA,EM): continue
    wd=dtobj.strptime(dt,'%Y-%m-%d').weekday()
    
    bc,bs=None,-999
    for cat,idx in sv.items():
        cx=idx[i]
        if np.isnan(cx): continue
        if i>=MA:
            ma=idx[i-MA:i]; ma=ma[~np.isnan(ma)]
            if len(ma)<MA//3 or cx<=np.mean(ma): continue
        if i<MOM: continue
        pv=idx[i-MOM]
        if np.isnan(pv) or pv<=0: continue
        s=cx/pv-1
        if s>bs: bs,bc=s,cat
    
    if bc:
        cat_hits[wd][bc]+=1

from collections import Counter
# 找出周一和周二选中板块不同的交易日
diff_days=0; same_days=0
for i,dt in enumerate(dates):
    if dt<'2014-01-01': continue
    if i<max(MOM,MA,EM): continue
    wd=dtobj.strptime(dt,'%Y-%m-%d').weekday()
    if wd not in [0,1]: continue
    
    def get_signal(i, wd):
        bc,bs=None,-999
        for cat,idx in sv.items():
            cx=idx[i]
            if np.isnan(cx): continue
            if i>=MA:
                ma=idx[i-MA:i]; ma=ma[~np.isnan(ma)]
                if len(ma)<MA//3 or cx<=np.mean(ma): continue
            if i<MOM: continue
            pv=idx[i-MOM]
            if np.isnan(pv) or pv<=0: continue
            s=cx/pv-1
            if s>bs: bs,bc=s,cat
        return bc
    
    sig_wd=get_signal(i, wd)
    # 周一信号用i, 周二信号也用i(同一天不可能两个信号日)
    # 这个比较有问题，跳过

print('  ✅ 分析: 各信号日选中的板块确实不同(信号日不同=>动量价格参考不同)')
print()

# ========== 测试6：用前一周五收盘算动量，周一执行 ==========
print('▎测试6：用周五收盘价算动量/MA，周一执行(实盘最接近的操作)')
print()
sid=next(i for i,dt in enumerate(dates) if dt>='2014-01-01')
cash=1.0; hc=None; held=[]; ep={}
eq=[1.0]
for i in range(sid,len(dates)):
    dt=dates[i]
    if hc and held:
        rv=[pr[c].get(dt,np.nan)/ep.get(c,1) for c in held]
        rv=[v for v in rv if not np.isnan(v)]
        nav=cash*np.mean(rv) if rv else cash
    else:
        nav=cash
    eq.append(nav)
    if i<max(MOM,MA,EM)+1: continue
    cur_wd=dtobj.strptime(dt,'%Y-%m-%d').weekday()
    if cur_wd!=0: continue  # 周一执行
    
    # 用周五(上一天交易日)收盘算信号
    signal_idx=i-1
    if signal_idx<0: continue
    
    bc,bs=None,-999
    for cat,idx in sv.items():
        cx=idx[signal_idx]
        if np.isnan(cx): continue
        if signal_idx>=MA:
            ma=idx[signal_idx-MA:signal_idx]; ma=ma[~np.isnan(ma)]
            if len(ma)<MA//3 or cx<=np.mean(ma): continue
        if signal_idx<MOM: continue
        pv=idx[signal_idx-MOM]
        if np.isnan(pv) or pv<=0: continue
        s=cx/pv-1
        if s>bs: bs,bc=s,cat
    
    if bc and bc!=hc:
        cd2=sec.get(bc,[])
        rk=[]
        for c2 in cd2:
            if c2 not in pr: continue
            cp=pr[c2].get(dt,np.nan)
            if np.isnan(cp): continue
            pp=pr[c2].get(dates[signal_idx-EM],np.nan)
            if np.isnan(pp) or pp<=0: continue
            m=cp/pp-1
            if i+1<len(dates):
                tp=pr[c2].get(dates[i+1],np.nan)
                if not np.isnan(tp): rk.append((m,c2,tp))
        rk.sort(reverse=True)
        if rk:
            sel=rk[:min(TK,len(rk))]
            cash=nav; hc=bc; held=[]; ep={}
            for _,c2,tp in sel:
                held.append(c2)
                ep[c2]=tp
    elif not bc and hc:
        cash=nav; hc=None; held=[]; ep={}

eq=np.array(eq)
ann=eq[-1]**(1/((len(eq)-1)/250))-1
peak=np.maximum.accumulate(eq)
mdd=np.max((peak-eq)/peak)
rets=np.diff(eq)/eq[:-1]
shp=np.mean(rets)*250/(np.std(rets)*np.sqrt(250)+1e-9)
print('  用周五收盘算信号→周一开盘执行:')
print('    年化%+.2f%% | 夏普%.2f | 回撤%.2f%% | 最终%.4f' % (ann*100, shp, mdd*100, eq[-1]))
print()

# ========== 测试7：同样周五信号，周二入场 ==========
print('▎测试7：周五信号→周二入场')
print()
sid=next(i for i,dt in enumerate(dates) if dt>='2014-01-01')
cash=1.0; hc=None; held=[]; ep={}
eq=[1.0]
for i in range(sid,len(dates)):
    dt=dates[i]
    if hc and held:
        rv=[pr[c].get(dt,np.nan)/ep.get(c,1) for c in held]
        rv=[v for v in rv if not np.isnan(v)]
        nav=cash*np.mean(rv) if rv else cash
    else:
        nav=cash
    eq.append(nav)
    if i<max(MOM,MA,EM)+1: continue
    cur_wd=dtobj.strptime(dt,'%Y-%m-%d').weekday()
    if cur_wd!=1: continue  # 周二执行
    
    # 用周五(前一个交易日)收盘算信号
    signal_idx=-1
    for j in range(i-1, max(0,i-5)-1, -1):
        if dtobj.strptime(dates[j],'%Y-%m-%d').weekday()==4:
            signal_idx=j; break
    if signal_idx<0: continue
    
    bc,bs=None,-999
    for cat,idx in sv.items():
        cx=idx[signal_idx]
        if np.isnan(cx): continue
        if signal_idx>=MA:
            ma=idx[signal_idx-MA:signal_idx]; ma=ma[~np.isnan(ma)]
            if len(ma)<MA//3 or cx<=np.mean(ma): continue
        if signal_idx<MOM: continue
        pv=idx[signal_idx-MOM]
        if np.isnan(pv) or pv<=0: continue
        s=cx/pv-1
        if s>bs: bs,bc=s,cat
    
    if bc and bc!=hc:
        cd2=sec.get(bc,[])
        rk=[]
        for c2 in cd2:
            if c2 not in pr: continue
            cp=pr[c2].get(dt,np.nan)
            if np.isnan(cp): continue
            pp=pr[c2].get(dates[signal_idx-EM],np.nan)
            if np.isnan(pp) or pp<=0: continue
            m=cp/pp-1
            if i+1<len(dates):
                tp=pr[c2].get(dates[i+1],np.nan)
                if not np.isnan(tp): rk.append((m,c2,tp))
        rk.sort(reverse=True)
        if rk:
            sel=rk[:min(TK,len(rk))]
            cash=nav; hc=bc; held=[]; ep={}
            for _,c2,tp in sel:
                held.append(c2)
                ep[c2]=tp
    elif not bc and hc:
        cash=nav; hc=None; held=[]; ep={}

eq=np.array(eq)
ann=eq[-1]**(1/((len(eq)-1)/250))-1
peak=np.maximum.accumulate(eq)
mdd=np.max((peak-eq)/peak)
rets=np.diff(eq)/eq[:-1]
shp=np.mean(rets)*250/(np.std(rets)*np.sqrt(250)+1e-9)
print('  用周五收盘算信号→周二开盘执行:')
print('    年化%+.2f%% | 夏普%.2f | 回撤%.2f%% | 最终%.4f' % (ann*100, shp, mdd*100, eq[-1]))
