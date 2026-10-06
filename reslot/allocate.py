import pandas as pd, numpy as np
bd=pd.read_pickle('bins.pkl'); rt=pd.read_pickle('racks.pkl'); sk=pd.read_pickle('sku.pkl'); inv=pd.read_pickle('inv.pkl')

FOOD={'Atta, Rice, Oil & Dals','Masala, Dry Fruits & More','Tea, Coffee & More','Breakfast & Sauces',
'Packaged Food','Munchies','Biscuits','Sweet Cravings','Cold Drinks & Juices','Protein & Nutrition',
'Dairy, Bread & Eggs','Fruits & Vegetables'}
BEAUTY_CATS={'Makeup & Beauty','Skincare','Fragrances & Grooming'}

# ---- category profile from REAL volume ----
prof=sk[sk.catEff!=''].groupby('unit').agg(
    skus=('sku_id','nunique'),
    pLARGE=('size',lambda s:s.isin(['LARGE','XL']).mean()),
    pSMALL=('size',lambda s:(s=='SMALL').mean())).reset_index()
prof=prof.rename(columns={'unit':'catEff'})
prof['parent']=prof.catEff.str.split(' :: ').str[0]
def ctier(r):
    if r.parent=='Premium Beauty': return 'BEAUTY'
    if r.parent=='Paan Corner': return 'PIN'
    if r.pLARGE>=0.30: return 'LARGE'
    if r.pSMALL>=0.70: return 'SMALL'
    return 'MED'
prof['tier']=prof.apply(ctier,axis=1); prof['food']=prof.parent.isin(FOOD)
prof['need']=np.ceil(prof.skus/0.80).astype(int)

# ---- rack capacity (usable = non-overhead comingle slots) ----
cap=bd[bd.cls!='OVERHEAD'].groupby('label').lim.sum()
rt['cap']=rt.label.map(cap).fillna(0).astype(int)
rt=rt.sort_values('seq').reset_index(drop=True)
PIN_PAAN=['J-1','J-3']; PIN_BEAUTY=['L-14','L-16','L-18']
BAT_BINS=set(bd[bd.binTypeCode=='D_BAT_1'].binCode)  # J-4/J-6 long-handle bins, reserved
rt=rt[~rt.label.isin(['J-15','J-17'])]       # tiny D_Cig bins left as-is
XLR=['N-5']  # reserve 1 D_LSS rack as shared XL pool; N-9/O-3/O-7 stay in general pool
free=rt[~rt.label.isin(PIN_PAAN+PIN_BEAUTY+XLR)].copy()
racks=free.to_dict('records')

# ---- placement: food first, tier-matched, MED/LARGE never on SMALL (D_140H) racks ----
assign={}
PREF={'LARGE':['LARGE','XL','MED','RESERVE'],'MED':['MED','LARGE','XL','RESERVE'],
      'SMALL':['SMALL','MED','LARGE','XL','RESERVE'],'XL':['XL','LARGE','MED','RESERVE']}
prof['fo']=(~prof.food).astype(int)
cats=prof[~prof.tier.isin(['BEAUTY','PIN'])].sort_values(['fo','parent','need'],ascending=[True,True,False])
def grab(cat,need,pref):
    got=sum(int(r['cap']) for r in racks if assign.get(r['label'])==cat)
    for tr in pref:
        if got>=need: break
        for r in racks:
            if r['label'] in assign or r['domtier']!=tr: continue
            assign[r['label']]=cat; got+=int(r['cap'])
            if got>=need: break
    return got
for _,c in cats.iterrows(): grab(c.catEff,c.need,PREF[c.tier])
for _,c in cats.iterrows():          # fallback for any unmet
    got=sum(int(r['cap']) for r in racks if assign.get(r['label'])==c.catEff)
    if got>=c.need: continue
    for r in racks:
        if r['label'] in assign or r['domtier'] not in PREF[c.tier]: continue
        assign[r['label']]=c.catEff; got+=int(r['cap'])
        if got>=c.need: break
# pins
for l in PIN_PAAN: assign[l]='Paan Corner'
for l in PIN_BEAUTY: assign[l]='Premium Beauty'
# D_LSS racks are a shared XL pool (any category's oversized SKUs) -> not category-assigned here
for l in XLR: assign.pop(l,None)

rt['category']=rt.label.map(assign)
rt.loc[rt.label.isin(XLR),'category']='XL Pool (D_LSS) — oversized'
rt['category']=rt.category.fillna('SPARE / GROWTH')
parent_of=prof.set_index('catEff').parent.to_dict()
rt['parent']=rt.category.map(lambda c:parent_of.get(c,c))
rt['zone']=np.where(rt.parent.isin(FOOD),'FOOD',np.where(rt.category=='SPARE / GROWTH','-','NON-FOOD'))
rt.to_pickle('racks_assigned.pkl'); prof.to_pickle('prof.pkl')
# checks
t=prof.set_index('catEff').tier.to_dict()
bad=[(r.label,r.category) for _,r in rt.iterrows() if r.domtier=='SMALL' and t.get(r.category) in ('MED','LARGE')]
print('MED/LARGE cats on SMALL(D_140H) racks:',bad)
print('unplaced:',set(prof.catEff)-set(rt.category)-{'Premium Beauty','Paan Corner'}|({'Premium Beauty'}-set(rt.category)))
print('spare racks:',(rt.category=='SPARE / GROWTH').sum())
print('J-1/3:',[assign.get(x) for x in ['J-1','J-3']],'| J-9/11/13:',[assign.get(x) for x in ['J-9','J-11','J-13']])
