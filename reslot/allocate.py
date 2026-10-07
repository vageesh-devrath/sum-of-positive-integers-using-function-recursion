import pandas as pd, numpy as np, os
bd=pd.read_pickle('bins.pkl'); rt=pd.read_pickle('racks.pkl'); sk=pd.read_pickle('sku.pkl'); inv=pd.read_pickle('inv.pkl')

FOOD={'Atta, Rice, Oil & Dals','Masala, Dry Fruits & More','Tea, Coffee & More','Breakfast & Sauces',
'Packaged Food','Munchies','Biscuits','Sweet Cravings','Cold Drinks & Juices','Protein & Nutrition',
'Dairy, Bread & Eggs','Fruits & Vegetables'}
BEAUTY_CATS={'Makeup & Beauty','Skincare','Fragrances & Grooming'}

# ---- category profile from REAL volume ----
sk['tv']=sk.vol.fillna(0).clip(lower=0)*sk.qty.fillna(0).clip(lower=1)   # stock volume (cc)
prof=sk[sk.catEff!=''].groupby('unit').agg(
    skus=('sku_id','nunique'),
    pLARGE=('size',lambda s:s.isin(['LARGE','XL']).mean()),
    pSMALL=('size',lambda s:(s=='SMALL').mean()),
    tv=('tv','sum')).reset_index()
prof=prof.rename(columns={'unit':'catEff'})
prof['parent']=prof.catEff.str.split(' :: ').str[0]
def ctier(r):
    if r.parent=='Premium Beauty': return 'BEAUTY'
    if r.parent=='Paan Corner': return 'PIN'
    if r.pLARGE>=0.30: return 'LARGE'
    if r.pSMALL>=0.70: return 'SMALL'
    return 'MED'
prof['tier']=prof.apply(ctier,axis=1); prof['food']=prof.parent.isin(FOOD)
prof['need']=np.ceil(prof.skus/0.80).astype(int)          # comingle slots, 80% target
prof['needv']=prof.tv/0.95                                   # stock volume, 95% of physical bin volume

# ---- rack capacity (usable = non-overhead comingle slots + bin volume) ----
cap=bd[bd.cls!='OVERHEAD'].groupby('label').lim.sum()
capv=bd[bd.cls!='OVERHEAD'].groupby('label').binvol.sum()
rt['cap']=rt.label.map(cap).fillna(0).astype(int); rt['capv']=rt.label.map(capv).fillna(0)
rt=rt.sort_values('seq').reset_index(drop=True)
PIN_PAAN=['J-1','J-3']; PIN_BEAUTY=['L-14','L-16','L-18']
BATR=sorted(bd[bd.binTypeCode=='D_BAT_1'].label.unique())       # J-4/J-6: long-handle tool bins only
CIGR=['J-15','J-17']                                              # tiny D_Cig bins left as-is
FIXED=PIN_PAAN+PIN_BEAUTY+BATR+CIGR
free=rt[~rt.label.isin(FIXED)].copy()
racks=free.to_dict('records')

# ---- order units so each category (and its dedicated subcats) is ONE consecutive run of racks ----
# position = where the unit's stock sits today (median rack seq) -> fewer, shorter moves
seq=rt.set_index('label').seq.to_dict()
pos=inv.assign(s=inv.label.map(seq),unit=inv.sku_id.map(sk.set_index('sku_id').unit)).groupby('unit').s.median()
prof['pos']=prof.catEff.map(pos).fillna(1e9)
ppos=prof.groupby('parent').pos.median()
prof['ppos']=prof.parent.map(ppos)
prof['fo']=prof.food.astype(int)
prof['is_sub']=prof.catEff.str.contains(' :: ')
cats=prof[~prof.tier.isin(['BEAUTY','PIN'])].sort_values(['fo','ppos','parent','is_sub','pos'])   # non-food run, then food run
pd.to_pickle(dict(units=list(cats.catEff),racks=[r['label'] for r in racks]),'order.pkl')
assign={}

# pins
for l in PIN_PAAN: assign[l]='Paan Corner'
for l in PIN_BEAUTY: assign[l]='Premium Beauty'
for l in BATR: assign[l]='Long-handle Tools (D_BAT)'

rt['category']=rt.label.map(assign)
rt.loc[rt.label.isin(CIGR),'category']='NOT USED (D_Cig)'
parent_of=prof.set_index('catEff').parent.to_dict()
rt['parent']=rt.category.map(lambda c:parent_of.get(c,c))
rt['zone']=np.where(rt.parent.isin(FOOD),'FOOD',np.where(rt.category.fillna('NOT USED').str.startswith('NOT USED'),'-','NON-FOOD'))
rt.to_pickle('racks_assigned.pkl'); prof.to_pickle('prof.pkl')
print('unit order (floor sequence):',list(cats.catEff))
