import pandas as pd, numpy as np
bd=pd.read_pickle('bins.pkl'); rt=pd.read_pickle('racks_assigned.pkl'); sk=pd.read_pickle('sku.pkl'); inv=pd.read_pickle('inv.pkl'); prof=pd.read_pickle('prof.pkl')
FOOD=set(prof[prof.food].parent)|{'Fruits & Vegetables','Dairy, Bread & Eggs'}
BEAUTY_CATS={'Makeup & Beauty','Skincare','Fragrances & Grooming'}
sk['catEff']=np.where(sk.category_name.isin(BEAUTY_CATS),'Premium Beauty',sk.category_name)
# 'unit' already in sku.pkl (catEff or 'catEff :: subcat')
bd.loc[bd.binTypeCode=='D_BAT_1','cls']='BAT'   # long-handle tool bins (J-4/J-6)
od=pd.read_pickle('order.pkl')
lab2cat={l:c for l,c in rt.set_index('label').category.items() if isinstance(c,str) and not c.startswith('NOT USED')}
def parent_of(c): return str(c).split(' :: ')[0]
PINNED={'Paan Corner','Premium Beauty'}

sk['parent']=sk.unit.str.split(' :: ').str[0]
sk['restrict']=sk.liquid | (sk.parent=='Premium Beauty') | (sk.parent=='Paan Corner')
sk['vol']=sk.vol.fillna(0).clip(lower=0)
inv['sku_vol_cc']=inv.sku_id.map(sk.set_index('sku_id').vol)   # one unit volume per SKU everywhere
sk['qty']=sk.qty.fillna(0).clip(lower=1).astype(int)
sk['tv']=sk.vol*sk.qty                    # total stock volume of the SKU on floor 2 (cc)

# ---- bin state: comingle slots + physical volume (btc_vol_cc) left ----
S={r.binCode:dict(slots=int(r.lim),vol=float(r.binvol),cap=float(r.binvol),cls=r.cls,label=r.label)
   for r in bd.itertuples()}
rack_bins=bd.groupby('label').binCode.apply(list).to_dict()
cur_bins=inv.groupby('sku_id').bin_code.apply(list).to_dict()

def place(sid,unitvol,qty,cands,volcheck=True):
    """Put qty units of a SKU into cands (in order). One bin if it fits, else split
    across several. All-or-nothing: returns [(bin,qty)] or None."""
    tv=unitvol*qty
    for b in cands:                                       # single bin first
        s=S[b]
        if s['slots']>0 and s['cap']>=unitvol and (not volcheck or s['vol']>=tv):
            s['slots']-=1; s['vol']-=tv; return [(b,qty)]
    left=qty; got=[]
    for b in cands:                                       # split across bins
        s=S[b]
        if s['slots']<=0 or s['cap']<unitvol: continue
        n=left if (not volcheck or unitvol<=0) else min(left,int(s['vol']//unitvol))
        if n<1: continue
        got.append((b,n)); left-=n
        if left==0: break
    if left>0: return None
    for b,n in got: S[b]['slots']-=1; S[b]['vol']-=unitvol*n
    return got

def order(bins,seq,sid,anchor):
    rank={k:i for i,k in enumerate(seq)}; cur=set(cur_bins.get(sid,[]))
    bs=[b for b in bins if S[b]['cls'] in rank]
    return sorted(bs,key=lambda b:(b not in cur, S[b]['label']!=anchor, rank[S[b]['cls']], S[b]['cap']))

target={}; reason={}
def rule(r,parent,anchor):
    if parent=='Paan Corner': return ['LARGE','MED','SMALL','XL','CIG'],'Paan/HVP -> J-1/J-3, no overhead/reserve'
    if parent=='Premium Beauty': return ['BEAUTY','MED','LARGE','SMALL'],'Premium beauty -> D_BEAUTY, no overhead/reserve'
    if r.restrict: return (['SMALL','MED','LARGE','XL'] if r.size=='SMALL' else ['MED','LARGE','XL','SMALL']),'Liquid -> shelf, no overhead/deep-reserve'
    if r.size in ('LARGE','XL'): return ['XL','LARGE','RESERVE','MED'],'Large/XL vol -> XL/large bin'
    if r.size=='MED': return ['MED','LARGE','XL','RESERVE'],'Medium vol -> med/large bin'
    return ['SMALL','MED','LARGE','XL','RESERVE'],('Co-located' if anchor else 'Small vol -> panda/shelf cell')

# ---- long-handle floor tools -> D_BAT bins (J-4/J-6); comingle-governed, not volume ----
bat=[b for b,s_ in S.items() if s_['cls']=='BAT']
for r in sk[sk.bat].sort_values('vol',ascending=False).itertuples():
    t=place(r.sku_id,0,r.qty,bat,volcheck=False)
    if t: target[r.sku_id]=t; reason[r.sku_id]='Long-handle tool -> D_BAT bin (J-4/J-6)'

def fill(unit,grp,racks_open,next_rack):
    """Pack a unit's SKUs (biggest stock first) into its open racks; open the next consecutive
    rack only when a SKU fits nowhere in the block. Returns racks used."""
    parent=parent_of(unit)
    for r in grp[~grp.sku_id.isin(target)].sort_values('tv',ascending=False).itertuples():
        while True:
            bins=[b for l in racks_open for b in rack_bins[l] if S[b]['cls']!='BAT']
            anchor=next((l for l in racks_open if l in r.cur),None)
            seq,why=rule(r,parent,anchor)
            t=place(r.sku_id,r.vol,r.qty,order(bins,seq,r.sku_id,anchor))
            if t is None and not r.restrict and r.size in ('LARGE','XL'):   # bulky: overhead of own block before a new rack
                t=place(r.sku_id,r.vol,r.qty,order(bins,['OVERHEAD'],r.sku_id,anchor)); why+=' | overhead reserve'
            if t: target[r.sku_id]=t; reason[r.sku_id]=why; break
            l=next_rack()
            if l is None:                                        # floor full: last resort = overhead of own block
                if not r.restrict:
                    t=place(r.sku_id,r.vol,r.qty,order(bins,['OVERHEAD'],r.sku_id,anchor))
                    if t: target[r.sku_id]=t; reason[r.sku_id]=why+' | overhead reserve'; break
                target[r.sku_id]=[('OVERFLOW',r.qty)]; reason[r.sku_id]='No space left on floor 2 for own category block'; break
            racks_open.append(l)
    return racks_open

# ---- pinned blocks (Paan J-1/J-3, Premium Beauty L-14/16/18) ----
for unit in ['Paan Corner','Premium Beauty']:
    fixed=[l for l,c in lab2cat.items() if c==unit]
    fill(unit,sk[sk.unit==unit],fixed,lambda:None)

# ---- every other unit: one consecutive run of racks in floor order, sized by actual packing ----
free=list(od['racks']); ptr=[0]
def nxt():
    if ptr[0]>=len(free): return None
    l=free[ptr[0]]; ptr[0]+=1; return l
rack_units={}                                   # rack -> units on it (2 only on a shared boundary rack)
FOODU=lambda u: parent_of(u) in FOOD
prev=None
for unit in od['units']:
    grp=sk[(sk.unit==unit)&~sk.sku_id.isin(target)]
    if grp.empty: continue
    # the next unit starts on the previous unit's last rack when both are on the same side (food / non-food):
    # categories stay in one consecutive run, no half-empty tail racks, food and non-food never share a rack
    if prev and FOODU(prev[0])==FOODU(unit): opened=[prev[1]]
    else:
        l=nxt()
        if l is None:
            for s_ in grp.sku_id: target[s_]=[('OVERFLOW',int(sk.set_index('sku_id').qty[s_]))]; reason[s_]='No space left on floor 2 for own category block'
            continue
        opened=[l]
    for l in opened: rack_units.setdefault(l,[]).append(unit)
    n0=len(opened)
    def nxt_u(u=unit):
        l=nxt()
        if l is not None: rack_units.setdefault(l,[]).append(u)
        return l
    used=fill(unit,grp,opened,nxt_u)
    # drop the shared rack from this unit if it placed nothing there
    if n0 and not any(S_lab==used[0] for S_lab in (S[b]['label'] for s_ in grp.sku_id for b,_ in target.get(s_,[]) if b in S)):
        rack_units[used[0]].remove(unit)
    prev=(unit,used[-1])
spare=free[ptr[0]:]
for l in spare: rack_units[l]=['SPARE / GROWTH']
for l,us in rack_units.items(): lab2cat[l]=' + '.join(us)
print('racks used:',ptr[0],'of',len(free),'| spare racks at end:',spare,'| shared boundary racks:',sum(len(u)>1 for u in rack_units.values()))
# ---- write final rack -> category map ----
rt['category']=rt.label.map(lab2cat).fillna(rt.category)
pof=prof.set_index('catEff').parent.to_dict()
rt['parent']=rt.category.map(lambda c:' + '.join(dict.fromkeys(pof.get(x,x) for x in str(c).split(' + '))))
rt['zone']=np.where(rt.parent.map(lambda p:parent_of(p.split(' + ')[0]) in FOOD),'FOOD',np.where(rt.category.str.startswith(('NOT USED','SPARE')),'-','NON-FOOD'))
rt.to_pickle('racks_assigned.pkl')

# ---- move list: source (bin,qty) rows -> target (bin,qty), same bin matched first ----
binrac=bd.set_index('binCode')
skinfo=sk.set_index('sku_id')
rows=[]
for sid,g in inv.groupby('sku_id'):
    src=[[b,int(q)] for b,q in zip(g.bin_code,g.live_inv_qty.fillna(0).clip(lower=0).astype(int))]
    tgt=[[b,int(q)] for b,q in target.get(sid,[('OVERFLOW',int(skinfo.qty.get(sid,1)))])]
    if sum(q for _,q in src)==0:
        rows.append((sid,src[0][0],tgt[0][0],0)); continue
    for s_ in src:                                       # stock already in a target bin stays
        for t_ in tgt:
            if s_[0]==t_[0] and s_[1]>0 and t_[1]>0:
                n=min(s_[1],t_[1]); rows.append((sid,s_[0],t_[0],n)); s_[1]-=n; t_[1]-=n
    for s_ in src:
        for t_ in tgt:
            if s_[1]<=0: break
            if t_[1]<=0: continue
            n=min(s_[1],t_[1]); rows.append((sid,s_[0],t_[0],n)); s_[1]-=n; t_[1]-=n
        if s_[1]>0: rows.append((sid,s_[0],tgt[-1][0],s_[1]))
mv=pd.DataFrame(rows,columns=['sku_id','bin_code','To Bin','live_inv_qty'])
first=inv.drop_duplicates('sku_id').set_index('sku_id')
for c in ['product_name','category_name','subcategory_name','sku_vol_cc']: mv[c]=mv.sku_id.map(first[c])
mv['label']=mv.bin_code.map(binrac.label)
mv['catEff']=mv.sku_id.map(skinfo.catEff)
mv['Rule']=mv.sku_id.map(reason)
mv['To Rack']=mv['To Bin'].map(binrac.label).fillna('-')
mv['To Bin Class']=mv['To Bin'].map(bd.set_index('binCode').cls).fillna('-')
mv['To Category']=np.where(mv['To Rack']=='-','-',mv.sku_id.map(skinfo.unit))
mv.loc[mv.Rule.str.startswith('Long-handle',na=False),'To Category']='Long-handle Tools (D_BAT)'
mv['Move?']=np.where(mv.bin_code==mv['To Bin'],'No','Yes')
mv['size']=mv.sku_id.map(skinfo['size'])
mv['Move Vol cc']=(mv.live_inv_qty*mv.sku_vol_cc).round(0)
mv.to_pickle('packed.pkl')

# ---- checks ----
dry2=set(bd.binCode)
end=mv[mv['To Bin'].isin(dry2)]
occ=end.groupby('To Bin').agg(n=('sku_id','nunique'),v=('Move Vol cc','sum'))
lim=bd.set_index('binCode').lim; vol=bd.set_index('binCode').binvol; cls=bd.set_index('binCode').cls
occ['v']=end.assign(x=end.live_inv_qty*end.sku_vol_cc).groupby('To Bin').x.sum()
nb=occ[cls.reindex(occ.index)!='BAT']
print('rows touching non-floor-2 bins:',int((~mv.bin_code.isin(dry2)).sum()+(~mv['To Bin'].isin(dry2|{'OVERFLOW'})).sum()))
print('overflow SKUs:',mv[mv['To Bin']=='OVERFLOW'].sku_id.nunique())
print('comingle breaches:',int((occ.n>lim.reindex(occ.index)).sum()))
print('bin volume breaches (stock vol > btc, excl D_BAT):',int((nb.v>vol.reindex(nb.index)+1).sum()))
print('unit-volume breaches (excl D_BAT):',int(((end['To Bin'].map(vol)<end.sku_vol_cc)&(end['To Bin Class']!='BAT')).sum()))
print('restricted in overhead/reserve:',int((end.sku_id.map(skinfo.restrict)&end['To Bin Class'].isin(['OVERHEAD','RESERVE'])).sum()))
print('Paan in J-1/J-3:',round(end[end.catEff=='Paan Corner']['To Rack'].isin(['J-1','J-3']).mean()*100,1),'%')
print('split SKUs (>1 target bin):',int((end.groupby('sku_id')['To Bin'].nunique()>1).sum()))
print('rules:',{k:int(v) for k,v in mv.drop_duplicates('sku_id').Rule.str.split(' \\| ').str[-1].value_counts().items()})
print('total move rows:',int((mv['Move?']=='Yes').sum()),'| units moved:',int(mv[mv['Move?']=='Yes'].live_inv_qty.sum()))
