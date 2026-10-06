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

# bin volume ceilings per class (what a bin of this class can hold, cc)
BINVOL={'SMALL':6337,'BEAUTY':3168,'MED':20000,'LARGE':28800,'XL':60480,'RESERVE':38000,'OVERHEAD':1440000,'CIG':5000,'BAT':50000}
sk['parent']=sk.unit.str.split(' :: ').str[0]
sk['restrict']=sk.liquid | (sk.parent=='Premium Beauty') | (sk.parent=='Paan Corner')

target={}; reason={}
# ---- long-handle floor tools (mops/brooms/wipers) -> D_BAT bins (J-4/J-6) ----
batbins=[[r.binCode,int(r.lim),r.label] for _,r in bd[bd.cls=='BAT'].iterrows()]
xlbins=[[r.binCode,int(r.lim),r.label,r.binvol] for _,r in bd[bd.cls=='XLPOOL'].iterrows()]
for _,r in sk[(~sk.bat)&(sk.vol>22560)].sort_values('vol',ascending=False).iterrows():
    for x in xlbins:
        if x[1]>0 and x[3]>=r.vol: x[1]-=1; target[r.sku_id]=x[0]; reason[r.sku_id]='Oversized -> XL pool (D_LSS N-5)'; break
for _,r in sk[sk.bat].sort_values('vol',ascending=False).iterrows():
    done=False
    for x in batbins:
        if x[1]>0: x[1]-=1; target[r.sku_id]=x[0]; reason[r.sku_id]='Long-handle tool -> D_BAT bin (J-4/J-6)'; done=True; break
    if not done: target[r.sku_id]='OVERFLOW'; reason[r.sku_id]='Long-handle tool (D_BAT full)'

for cat,grp in sk.groupby('unit'):
    racks=[l for l,c in lab2cat.items() if c==cat]
    bins=bd[bd.label.isin(racks)].copy()
    if bins.empty:
        for s in grp.sku_id:
            if s not in target: target[s]='OVERFLOW'; reason[s]='no rack'
        continue
    buck={k:[] for k in ['SMALL','BEAUTY','MED','LARGE','XL','RESERVE','OVERHEAD','CIG']}
    for _,r in bins[~bins.cls.isin(['BAT','XLPOOL'])].sort_values('binvol').iterrows(): buck[r.cls].append([r.binCode,int(r.lim),r.label,r.binvol])
    def anch(cur): return next((l for l in racks if l in cur),None)
    def take(seq,vol,anchor,allow_overhead):
        # hard volume fit per ACTUAL bin volume (x[3]); never place a SKU in a bin smaller than it
        for pref_anchor in ([anchor,None] if anchor else [None]):
            for k in seq:
                if not allow_overhead and k in ('OVERHEAD',): continue
                for x in buck[k]:
                    if x[1]<=0 or x[3]<vol: continue
                    if pref_anchor and x[2]!=pref_anchor: continue
                    x[1]-=1; return x[0]
        return None
    g=grp[~grp.sku_id.isin(target)].copy(); g['a']=g.cur.map(anch)
    for _,r in g.sort_values('vol',ascending=False).iterrows():
        v=r.vol; a=r.a
        parent=cat.split(' :: ')[0]
        if parent=='Paan Corner':
            seq=['LARGE','MED','SMALL','XL']; why='Paan/HVP -> J-1/J-3, no overhead/reserve'
            t=take(seq,v,a,False)
        elif parent=='Premium Beauty':
            seq=['BEAUTY','MED','LARGE']; why='Premium beauty -> D_BEAUTY, no overhead/reserve'
            t=take(seq,v,a,False)
        elif r.restrict:                                  # liquids: no overhead, no reserve
            seq=['SMALL','MED','LARGE','XL'] if r['size']=='SMALL' else ['MED','LARGE','XL','SMALL']
            t=take(seq,v,a,False); why='Liquid -> shelf, no overhead/deep-reserve'
        elif r['size'] in ('LARGE','XL'):
            seq=['XL','LARGE','RESERVE','MED']; t=take(seq,v,a,True); why='Large/XL vol -> XL/large bin'
        elif r['size']=='MED':
            seq=['MED','LARGE','XL','RESERVE']; t=take(seq,v,a,True); why='Medium vol -> med/large bin'
        else:                                             # small
            seq=['SMALL','MED','LARGE','XL','RESERVE']; t=take(seq,v,a,True)
            why=('Co-located' if a else 'Small vol -> panda/shelf cell')
        # overhead only as final reserve for non-restricted bulky
        if t is None and not r.restrict:
            t=take(['OVERHEAD'],v,a,True); why+=' | overhead reserve'
        target[r.sku_id]=t if t else 'OVERFLOW'; reason[r.sku_id]=why

# ---- sweep: relocate overflow to nearest valid bin (same food/non-food), respecting volume+comingle ----
used={}
for s,t in target.items():
    if t!='OVERFLOW': used[t]=used.get(t,0)+1
binrac=bd.set_index('binCode')
allb=bd.copy(); allb['food']=allb.catrack.map(lambda c:str(c).split(' :: ')[0] in FOOD)
skinfo=sk.set_index('sku_id')
for s,t in list(target.items()):
    if t!='OVERFLOW': continue
    r=skinfo.loc[s]; isfood=r.parent in FOOD; restr=bool(r.restrict); v=r.vol
    ok=['SMALL','BEAUTY','MED','LARGE','XL'] if restr else ['SMALL','BEAUTY','MED','LARGE','XL','RESERVE','OVERHEAD']
    cand=allb[(allb.food==isfood)&(allb.cls.isin(ok))&(allb.binvol>=v)].sort_values('binvol')
    for _,bb in cand.iterrows():
        if used.get(bb.binCode,0)<bb.lim:
            target[s]=bb.binCode; used[bb.binCode]=used.get(bb.binCode,0)+1
            reason[s]=reason.get(s,'')+' | relocated (no fit in home block)'; break

# ---- build move list (row per sku-bin) ----
inv['catEff']=inv.sku_id.map(sk.set_index('sku_id').catEff)
inv['To Bin']=inv.sku_id.map(target); inv['Rule']=inv.sku_id.map(reason)
inv['To Rack']=inv['To Bin'].map(lambda x: binrac.label.get(x,'-') if x in binrac.index else '-')
inv['To Bin Class']=inv['To Bin'].map(lambda x: binrac.cls.get(x,'-') if x in binrac.index else '-')
inv['To Category']=inv['To Rack'].map(lab2cat).fillna('-')
inv['Move?']=np.where(inv.bin_code==inv['To Bin'],'No','Yes')
inv['size']=inv.sku_id.map(sk.set_index('sku_id')['size'])
inv.to_pickle('packed.pkl')

# checks
lim=bd.set_index('binCode').lim.to_dict()
over=sum(1 for bn,c in used.items() if bn in lim and c>lim[bn])
d140=set(bd[bd.binTypeCode=='D_140H_1'].binCode)
toobig=inv[(inv['To Bin'].isin(d140))&(inv['size'].isin(['MED','LARGE','XL']))].sku_id.nunique()
volbad=inv[inv['To Bin'].isin(binrac.index)]
volbad=(volbad['To Bin'].map(binrac.binvol)<volbad.sku_id.map(skinfo.vol)).sum()
restr_bad=inv[(inv.Rule.str.contains('Liquid|Paan|beauty',case=False,na=False))&(inv['To Bin Class'].isin(['OVERHEAD','RESERVE']))].sku_id.nunique()
mix=inv[inv['To Rack']!='-'].groupby('To Rack')['To Category'].nunique()
print('overflow:',(inv['To Bin']=='OVERFLOW').sum(),'| comingle breaches:',over)
print('volume-fit breaches:',volbad)
print('MED/LARGE/XL SKUs in D_140H cells:',toobig)
print('restricted in overhead/reserve:',restr_bad)
print('racks w/ >1 category:',(mix>1).sum())
print('Paan in J-1/J-3:',(inv[inv.catEff=='Paan Corner']['To Rack'].isin(['J-1','J-3'])).mean().round(3)*100,'%')
print('total moves:',(inv['Move?']=='Yes').sum())
