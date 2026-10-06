import pandas as pd, numpy as np
bd=pd.read_pickle('bins.pkl'); rt=pd.read_pickle('racks_assigned.pkl'); sk=pd.read_pickle('sku.pkl'); inv=pd.read_pickle('inv.pkl'); prof=pd.read_pickle('prof.pkl')
FOOD=set(prof[prof.food].parent)|{'Fruits & Vegetables'}
BEAUTY_CATS={'Makeup & Beauty','Skincare','Fragrances & Grooming'}
sk['catEff']=np.where(sk.category_name.isin(BEAUTY_CATS),'Premium Beauty',sk.category_name)
# 'unit' already in sku.pkl (catEff or 'catEff :: subcat')
lab2cat=rt.set_index('label').category.to_dict()
bd['catrack']=bd.label.map(lab2cat)
bd.loc[bd.binTypeCode=='D_BAT_1','cls']='BAT'   # long-handle tool bins (J-4/J-6)
bd.loc[(bd.binTypeCode=='D_LSS')&(bd.label=='N-5'),'cls']='XLPOOL'  # shared oversized pool
bd['parent']=bd.catrack.map(lambda c:str(c).split(' :: ')[0])
bd['food']=bd.parent.isin(FOOD)
PINNED={'Paan Corner','Premium Beauty'}

sk['parent']=sk.unit.str.split(' :: ').str[0]
sk['restrict']=sk.liquid | (sk.parent=='Premium Beauty') | (sk.parent=='Paan Corner')
sk['vol']=sk.vol.fillna(0).clip(lower=0)
inv['sku_vol_cc']=inv.sku_id.map(sk.set_index('sku_id').vol)   # one unit volume per SKU everywhere
sk['qty']=sk.qty.fillna(0).clip(lower=1).astype(int)
sk['tv']=sk.vol*sk.qty                    # total stock volume of the SKU on floor 2 (cc)

# ---- bin state: comingle slots + physical volume (btc_vol_cc) left ----
S={r.binCode:dict(slots=int(r.lim),vol=float(r.binvol),cap=float(r.binvol),cls=r.cls,label=r.label,food=bool(r.food),parent=r.parent)
   for r in bd.itertuples()}
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
# ---- oversized (unit > 22,560cc) -> shared XL pool N-5 ----
xl=[b for b,s in S.items() if s['cls']=='XLPOOL']
for r in sk[(~sk.bat)&(sk.vol>22560)].sort_values('tv',ascending=False).itertuples():
    t=place(r.sku_id,r.vol,r.qty,sorted(xl,key=lambda b:S[b]['vol']))
    if t: target[r.sku_id]=t; reason[r.sku_id]='Oversized -> XL pool (D_LSS N-5)'
# ---- long-handle floor tools -> D_BAT bins (J-4/J-6); comingle-governed, not volume ----
bat=[b for b,s in S.items() if s['cls']=='BAT']
for r in sk[sk.bat].sort_values('vol',ascending=False).itertuples():
    t=place(r.sku_id,0,r.qty,bat,volcheck=False)
    if t: target[r.sku_id]=t; reason[r.sku_id]='Long-handle tool -> D_BAT bin (J-4/J-6)'

# ---- home block packing, biggest stock first ----
for cat,grp in sk.groupby('unit'):
    racks=[l for l,c in lab2cat.items() if c==cat]
    bins=[b for b,s in S.items() if s['label'] in racks and s['cls'] not in ('BAT','XLPOOL')]
    parent=cat.split(' :: ')[0]
    for r in grp[~grp.sku_id.isin(target)].sort_values('tv',ascending=False).itertuples():
        anchor=next((l for l in racks if l in r.cur),None)
        if parent=='Paan Corner':
            seq=['LARGE','MED','SMALL','XL','CIG']; why='Paan/HVP -> J-1/J-3, no overhead/reserve'
        elif parent=='Premium Beauty':
            seq=['BEAUTY','MED','LARGE','SMALL']; why='Premium beauty -> D_BEAUTY, no overhead/reserve'
        elif r.restrict:
            seq=['SMALL','MED','LARGE','XL'] if r.size=='SMALL' else ['MED','LARGE','XL','SMALL']; why='Liquid -> shelf, no overhead/deep-reserve'
        elif r.size in ('LARGE','XL'):
            seq=['XL','LARGE','RESERVE','MED']; why='Large/XL vol -> XL/large bin'
        elif r.size=='MED':
            seq=['MED','LARGE','XL','RESERVE']; why='Medium vol -> med/large bin'
        else:
            seq=['SMALL','MED','LARGE','XL','RESERVE']; why='Co-located' if anchor else 'Small vol -> panda/shelf cell'
        t=place(r.sku_id,r.vol,r.qty,order(bins,seq,r.sku_id,anchor))
        if t is None and not r.restrict:                  # overhead = last reserve for non-restricted
            t=place(r.sku_id,r.vol,r.qty,order(bins,['OVERHEAD'],r.sku_id,anchor)); why+=' | overhead reserve'
        if t: target[r.sku_id]=t; reason[r.sku_id]=why

# ---- sweep (floor 2 only): same parent block -> stay in current bin -> nearest same-zone bin ----
NOPEN={'BAT','XLPOOL'}
for r in sk[~sk.sku_id.isin(target)].sort_values('tv',ascending=False).itertuples():
    ok={'SMALL','BEAUTY','MED','LARGE','XL','CIG'} if r.restrict else {'SMALL','BEAUTY','MED','LARGE','XL','RESERVE','OVERHEAD','CIG'}
    isfood=r.parent in FOOD
    base=[b for b,s in S.items() if s['cls'] in ok and s['food']==isfood and s['cls'] not in NOPEN
          and (s['parent'] not in PINNED or s['parent']==r.parent)]
    tries=[([b for b in base if S[b]['parent']==r.parent],' | spill within own category racks'),
           ([b for b in cur_bins.get(r.sku_id,[]) if b in S and S[b]['cls'] in ok and S[b]['food']==isfood],' | kept in current bin (no space in new block)'),
           (base,' | relocated to nearest same-zone bin (no space in own block)')]
    for cands,tag in tries:
        t=place(r.sku_id,r.vol,r.qty,sorted(cands,key=lambda b:S[b]['cap']))
        if t: target[r.sku_id]=t; reason[r.sku_id]=reason.get(r.sku_id,'')+tag; break
    else:
        target[r.sku_id]=[('OVERFLOW',r.qty)]; reason[r.sku_id]='No floor-2 bin with free volume + comingle slot'

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
mv['To Category']=mv['To Rack'].map(lab2cat).fillna('-')
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
