"""QDII清理 + 信号日对比（修复版）"""
import json, os, numpy as np
from collections import defaultdict
from datetime import datetime as dtobj
import sys
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR=r'D:\Qclaw_Trading\data\history'
CAT_FILE=r'D:\Qclaw_Trading\data\cat_assignment_full.json'
MOM,MA,EM,TK=15,175,28,3
EXTRA={'商品/周期/资源':['518880']}

with open(CAT_FILE,'r',encoding='utf-8') as f: raw=json.load(f)
cm={}
for kw,en in raw.get('assignments',{}).items():
    for e in en: cm[e[0]]=e[1]

# 真正的QDII（境外资产、T+0）
REAL_QDII={'510900','160140','513360','161130','520580','520830','520870','164824','159687','159561','513850','513080','513400','160125','160222','161126','161127','159941','513100','513500','513520','159659','159660','513030','513080','159866'}
# 保留：164701(黄金LOF, 境内), 160719(黄金LOF, 境内), 161116(黄金主题LOF, 境内)
# 保留：160216(国泰商品, 境内), 161815(抗通胀, 境内), 165513(商品LOF, 境内)

sec=defaultdict(list)
for c,ct in cm.items():
    if ct=='海外/跨境': continue
    if c in REAL_QDII: continue
    sec[ct].append(c)
for cat,cs in EXTRA.items():
    for c in cs:
        if c not in sec[cat]: sec[cat].append(c)

print('板块信息:')
for k,v in sorted(sec.items(), key=lambda x:-len(x[1])):
    print('  %s: %d只' % (k, len(v)))
print()

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
    arr=[None]*len(dates)
    for i,dt in enumerate(dates):
        vals=[pr[c].get(dt,None) for c in cs if c in pr]
        vv=[v for v in vals if v is not None]
        arr[i]=sum(vv)/len(vv) if len(vv)>=max(1,len(cs)//3) else None
    sv[cat]=arr

def pick_sector_idx(i):
    bc,bs=None,-999
    for cat,idx in sv.items():
        cx=idx[i]
        if cx is None: continue
        if i>=MA:
            ma=[v for v in idx[i-MA:i] if v is not None]
            if len(ma)<MA//3 or cx<=sum(ma)/len(ma): continue
        if i<MOM: continue
        pv=idx[i-MOM]
        if pv is None or pv<=0: continue
        s=cx/pv-1
        if s>bs: bs,bc=s,cat
    return bc

# ========== 信号日对比 ==========
def run_bt(signal_wd, entry_offset=1):
    sid=next(i for i,dt in enumerate(dates) if dt>='2014-01-01')
    cash=1.0; hc=None; held=[]; ep={}
    eq=[1.0]
    for i in range(sid,len(dates)):
        dt=dates[i]
        if hc and held:
            rv=[]
            for c in held:
                cp=pr[c].get(dt,None)
                epv=ep.get(c,None)
                if cp is not None and epv is not None and epv>0:
                    rv.append(cp/epv)
            nav=cash*np.mean(rv) if rv else cash
        else: nav=cash
        eq.append(nav)
        if i<max(MOM,MA,EM): continue
        if dtobj.strptime(dt,'%Y-%m-%d').weekday()!=signal_wd: continue
        bc=pick_sector_idx(i)
        if bc and bc!=hc:
            cd2=sec.get(bc,[]); rk=[]
            for c2 in cd2:
                if c2 not in pr: continue
                cp=pr[c2].get(dt,None)
                if cp is None: continue
                pp=pr[c2].get(dates[i-EM],None)
                if pp is None or pp<=0: continue
                m=cp/pp-1
                entry_idx=i+entry_offset
                if entry_idx>=len(dates): continue
                tp=pr[c2].get(dates[entry_idx],None)
                if tp is not None: rk.append((m,c2,tp))
            rk.sort(reverse=True)
            if rk:
                sel=rk[:min(TK,len(rk))]
                cash=nav; hc=bc; held=[]; ep={}
                for _,c2,tp in sel:
                    held.append(c2); ep[c2]=tp
        elif not bc and hc:
            cash=nav; hc=None; held=[]; ep={}
    eq=np.array(eq)
    ann=eq[-1]**(1/((len(eq)-1)/250))-1 if len(eq)>1 else 0
    return ann

# 原始（含隐藏QDII的金融板块）
print('='*65)
print('  A: 原始板块映射（含隐藏QDII——金融=160140+510900）')
print('='*65)
sec_orig=defaultdict(list)
for c,ct in cm.items():
    if ct!='海外/跨境': sec_orig[ct].append(c)
for cat,cs in EXTRA.items():
    for c in cs:
        if c not in sec_orig[cat]: sec_orig[cat].append(c)
pr_orig={}
for codes in sec_orig.values():
    for c in codes:
        if c not in pr_orig:
            r=load_r(c)
            if r: pr_orig[c]={rr['date']:rr.get('close',0) for rr in r}
sv_orig={}
for cat,cs in sec_orig.items():
    arr=[None]*len(dates)
    for i,dt in enumerate(dates):
        vals=[pr_orig[c].get(dt,None) for c in cs if c in pr_orig]
        vv=[v for v in vals if v is not None]
        arr[i]=sum(vv)/len(vv) if len(vv)>=max(1,len(cs)//3) else None
    sv_orig[cat]=arr

def pick_sector_orig(i):
    bc,bs=None,-999
    for cat,idx in sv_orig.items():
        cx=idx[i]
        if cx is None: continue
        if i>=MA:
            ma=[v for v in idx[i-MA:i] if v is not None]
            if len(ma)<MA//3 or cx<=sum(ma)/len(ma): continue
        if i<MOM: continue
        pv=idx[i-MOM]
        if pv is None or pv<=0: continue
        s=cx/pv-1
        if s>bs: bs,bc=s,cat
    return bc

def run_bt_orig(signal_wd):
    sid=next(i for i,dt in enumerate(dates) if dt>='2014-01-01')
    cash=1.0; hc=None; held=[]; ep={}
    eq=[1.0]
    for i in range(sid,len(dates)):
        dt=dates[i]
        if hc and held:
            rv=[]
            for c in held:
                cp=pr_orig[c].get(dt,None)
                epv=ep.get(c,None)
                if cp is not None and epv is not None and epv>0:
                    rv.append(cp/epv)
            nav=cash*np.mean(rv) if rv else cash
        else: nav=cash
        eq.append(nav)
        if i<max(MOM,MA,EM): continue
        if dtobj.strptime(dt,'%Y-%m-%d').weekday()!=signal_wd: continue
        bc=pick_sector_orig(i)
        if bc and bc!=hc:
            cd2=sec_orig.get(bc,[]); rk=[]
            for c2 in cd2:
                if c2 not in pr_orig: continue
                cp=pr_orig[c2].get(dt,None)
                if cp is None: continue
                pp=pr_orig[c2].get(dates[i-EM],None)
                if pp is None or pp<=0: continue
                m=cp/pp-1
                entry_idx=i+1
                if entry_idx>=len(dates): continue
                tp=pr_orig[c2].get(dates[entry_idx],None)
                if tp is not None: rk.append((m,c2,tp))
            rk.sort(reverse=True)
            if rk:
                sel=rk[:min(TK,len(rk))]
                cash=nav; hc=bc; held=[]; ep={}
                for _,c2,tp in sel:
                    held.append(c2); ep[c2]=tp
        elif not bc and hc:
            cash=nav; hc=None; held=[]; ep={}
    eq=np.array(eq)
    ann=eq[-1]**(1/((len(eq)-1)/250))-1 if len(eq)>1 else 0
    return ann

for wd,lb in [(0,'周一'),(1,'周二'),(2,'周三'),(3,'周四'),(4,'周五')]:
    a=run_bt_orig(wd)
    print('  %s: 年化%+.2f%%' % (lb, a*100))

print()
print('='*65)
print('  B: 清理真实QDII后（金融板块空了）')
print('='*65)
for wd,lb in [(0,'周一'),(1,'周二'),(2,'周三'),(3,'周四'),(4,'周五')]:
    a=run_bt(wd)
    print('  %s: 年化%+.2f%%' % (lb, a*100))

print()
print('='*65)
print('  C: 清理QDII + 重新选金融ETF（银行512800+证券512880代替）')
print('='*65)
sec_new=defaultdict(list)
for c,ct in cm.items():
    if ct=='海外/跨境': continue
    if c in REAL_QDII: continue
    sec_new[ct].append(c)
# 用真实的金融ETF替换
sec_new['金融']=['512800','512880']  # 银行ETF+证券ETF
for cat,cs in EXTRA.items():
    for c in cs:
        if c not in sec_new[cat]: sec_new[cat].append(c)

print('  新金融板块:', sec_new['金融'])
for k,v in sorted(sec_new.items(), key=lambda x:-len(x[1])):
    print('  %s: %d只' % (k, len(v)))
print()

pr_new={}
for codes in sec_new.values():
    for c in codes:
        if c not in pr_new:
            r=load_r(c)
            if r: pr_new[c]={rr['date']:rr.get('close',0) for rr in r}

sv_new={}
for cat,cs in sec_new.items():
    arr=[None]*len(dates)
    for i,dt in enumerate(dates):
        vals=[pr_new[c].get(dt,None) for c in cs if c in pr_new]
        vv=[v for v in vals if v is not None]
        arr[i]=sum(vv)/len(vv) if len(vv)>=max(1,len(cs)//3) else None
    sv_new[cat]=arr

def run_bt_new(signal_wd):
    sid=next(i for i,dt in enumerate(dates) if dt>='2014-01-01')
    cash=1.0; hc=None; held=[]; ep={}
    eq=[1.0]
    for i in range(sid,len(dates)):
        dt=dates[i]
        if hc and held:
            rv=[]
            for c in held:
                cp=pr_new[c].get(dt,None)
                epv=ep.get(c,None)
                if cp is not None and epv is not None and epv>0:
                    rv.append(cp/epv)
            nav=cash*np.mean(rv) if rv else cash
        else: nav=cash
        eq.append(nav)
        if i<max(MOM,MA,EM): continue
        if dtobj.strptime(dt,'%Y-%m-%d').weekday()!=signal_wd: continue
        bc=None; bs=-999
        for cat,idx in sv_new.items():
            cx=idx[i]
            if cx is None: continue
            if i>=MA:
                ma=[v for v in idx[i-MA:i] if v is not None]
                if len(ma)<MA//3 or cx<=sum(ma)/len(ma): continue
            if i<MOM: continue
            pv=idx[i-MOM]
            if pv is None or pv<=0: continue
            s=cx/pv-1
            if s>bs: bs,bc=s,cat
        if bc and bc!=hc:
            cd2=sec_new.get(bc,[]); rk=[]
            for c2 in cd2:
                if c2 not in pr_new: continue
                cp=pr_new[c2].get(dt,None)
                if cp is None: continue
                pp=pr_new[c2].get(dates[i-EM],None)
                if pp is None or pp<=0: continue
                m=cp/pp-1
                entry_idx=i+1
                if entry_idx>=len(dates): continue
                tp=pr_new[c2].get(dates[entry_idx],None)
                if tp is not None: rk.append((m,c2,tp))
            rk.sort(reverse=True)
            if rk:
                sel=rk[:min(TK,len(rk))]
                cash=nav; hc=bc; held=[]; ep={}
                for _,c2,tp in sel:
                    held.append(c2); ep[c2]=tp
        elif not bc and hc:
            cash=nav; hc=None; held=[]; ep={}
    eq=np.array(eq)
    ann=eq[-1]**(1/((len(eq)-1)/250))-1 if len(eq)>1 else 0
    return ann

for wd,lb in [(0,'周一'),(1,'周二'),(2,'周三'),(3,'周四'),(4,'周五')]:
    a=run_bt_new(wd)
    print('  %s: 年化%+.2f%%' % (lb, a*100))
