import pandas as pd, numpy as np
import os
b=pd.read_csv(os.environ.get('RESLOT_BINS','/mnt/user-data/uploads/BIN_DOWNLOAD_BIN_DOWNLOAD_2026-10-06T09-47-23_256706_6C6BD.csv'),low_memory=False)
i=pd.read_csv(os.environ.get('RESLOT_INV','/mnt/user-data/uploads/sqllab_untitled_query_134_20261006T094554.csv'),low_memory=False)
i.columns=[c.strip().replace('﻿','') for c in i.columns]

# ---------- BINS (Dry_2 / floor 2) ----------
bd=b[b.zoneCode=='Dry_2'].copy()
bd=bd[bd.binCode.str.startswith('JNB',na=False)]
bd['rack']=bd['rack'].astype(int); bd['label']=bd.aisle+'-'+bd.rack.astype(str)
bd['lim']=bd.commingleSKULimit.fillna(6).astype(int)
VOL={'D_BEAUTY':3168,'D_140H_1':6337,'D_225L_260H':18720,'D_300L_205H':19680,'Deep_Lower_400':21158,
'D_900L_400B':21600,'D_400D_1':22560,'D_300L_260H':24960,'D_400D_2':28800,'Deep_Lower_600':31737,
'D_600D_1':33840,'D_600D_2':43200,'D_LSS':60480,'Deep':1440000,'D_Cig_1':5000,'D_BAT_1':6000,
'D_UTILITY':6000,'Festive_Bin':6000,'D_Sampling':3000}
bd['binvol']=bd.binTypeCode.map(VOL).fillna(6000)
# bin class
def bcls(t):
    if t=='Deep': return 'OVERHEAD'
    if t in {'D_600D_1','D_600D_2','Deep_Lower_600'}: return 'RESERVE'
    if t=='D_LSS': return 'XL'
    if t=='D_BEAUTY': return 'BEAUTY'
    if t in {'D_400D_1','D_400D_2','Deep_Lower_400','D_900L_400B'}: return 'LARGE'
    if t in {'D_300L_205H','D_300L_260H','D_225L_260H'}: return 'MED'
    if t in {'D_140H_1','D_BAT_1','D_Sampling','D_UTILITY','Festive_Bin'}: return 'SMALL'
    if t=='D_Cig_1': return 'CIG'
    return 'MED'
bd['cls']=bd.binTypeCode.map(bcls)
bd.to_pickle('bins.pkl')

# rack dominant tier (exclude overhead) by total bin volume share
bx=bd[bd.cls!='OVERHEAD']
rt=bd.sort_values(['aisle','rack']).drop_duplicates('label')[['aisle','rack','label']].reset_index(drop=True)
rt['seq']=range(1,len(rt)+1)
dom=bx.groupby('label').apply(lambda g:g.groupby('cls').binvol.sum().idxmax(),include_groups=False).rename('domtier')
rt=rt.merge(dom,on='label',how='left')
rt['domtier']=rt.domtier.fillna('MED')
rt.to_pickle('racks.pkl')

# ---------- INVENTORY (map to Dry_2) ----------
d2=set(bd.binCode)
inv=i[i.bin_code.isin(d2)].copy()
inv['label']=inv.bin_code.map(bd.set_index('binCode').label)
# SKU master: real volume per unit, category, current bins
sk=(inv.groupby(['sku_id','product_name','category_name']).agg(
    vol=('sku_vol_cc','max'), qty=('live_inv_qty','sum'),
    cur=('label',lambda s:set(s))).reset_index())
sk=sk[sk.category_name.notna()]
# volume-based size tier (cc)
def szt(v):
    if v<2000: return 'SMALL'      # fits D_140H(6337)/D_BEAUTY(3168) cell with headroom
    if v<8000: return 'MED'        # needs D_300L/D_400D
    if v<30000: return 'LARGE'     # D_400D/D_600D
    return 'XL'                    # D_LSS / overhead
sk['size']=sk.vol.map(szt)
liqpat=r'liquid|oil|shampoo|juice|drink|sauce|phenyl|cleaner|lotion|serum|toner|syrup|wash|detergent|softener|handwash|bodywash|ml\b'
liqflag=inv.assign(l=inv.subcategory_name.fillna('').str.cat(inv.product_name.fillna(''),sep=' ').str.contains(liqpat,case=False)).groupby('sku_id').l.max()
sk['liquid']=sk.sku_id.map(liqflag).fillna(False).astype(bool)
# long-handle floor tools -> D_BAT bins
batpat=r'\b(?:broom|jhadu|spin mop|floor mop|bucket mop|microfiber mop|flat mop|wiper|squeegee|cobweb|mop stick|mop refill|mop rod|floor scrubber|ceiling broom)\b'
batexcl=r'lipstick|toothbrush|eyeshadow|eye shadow|makeup brush|nail|mascara|incense|dhoop|dandiya|wafer|kitchen wiper|sink wiper'
sk['bat']=sk.product_name.str.contains(batpat,case=False,na=False,regex=True)&~sk.product_name.str.contains(batexcl,case=False,na=False,regex=True)
# beauty + food helpers for unit calc
BEAUTY_CATS={'Makeup & Beauty','Skincare','Fragrances & Grooming'}
sk['catEff']=np.where(sk.category_name.isin(BEAUTY_CATS),'Premium Beauty',sk.category_name)
# dedicated subcategory units (>=150 SKUs), excluding pinned parents
subcnt=inv.groupby(['category_name','subcategory_name']).sku_id.nunique()
BIGSUB={(c,s2) for (c,s2),n in subcnt.items() if n>=150}
sub_of=inv.drop_duplicates('sku_id').set_index('sku_id').subcategory_name.to_dict()
def _unit(r):
    key=(r.category_name,sub_of.get(r.sku_id))
    if key in BIGSUB and r.catEff not in ('Premium Beauty','Paan Corner'):
        return f"{r.catEff} :: {sub_of.get(r.sku_id)}"
    return r.catEff
sk['unit']=sk.apply(_unit,axis=1)
sk.to_pickle('sku.pkl')
inv.to_pickle('inv.pkl')

print('Dry_2 bins:',len(bd),'| racks:',len(rt))
print('Dry_2 SKUs:',sk.sku_id.nunique(),'| inv rows:',len(inv))
print('size tiers:',dict(sk['size'].value_counts()))
print('rack dom tiers:',dict(rt.domtier.value_counts()))
