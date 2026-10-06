from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import pandas as pd, numpy as np, os
inv=pd.read_pickle('packed.pkl'); rt=pd.read_pickle('racks_assigned.pkl'); bd=pd.read_pickle('bins.pkl')
# relabel pure-D_BAT racks
batracks=bd.groupby('label').binTypeCode.apply(lambda s:set(s)=={'D_BAT_1'})
for l in batracks[batracks].index:
    rt.loc[rt.label==l,'category']='Long-handle Tools (D_BAT)'; rt.loc[rt.label==l,'zone']='NON-FOOD'
rt.to_pickle('racks_assigned.pkl')
seq=rt.set_index('label').seq.to_dict()
inv['To Category']=inv['To Rack'].map(rt.set_index('label').category.to_dict()).fillna('-')
# category/subcat plan
cp=rt[rt.category!='SPARE / GROWTH'].groupby('category').agg(
    Racks=('label','count'),From=('label',lambda s:sorted(s,key=lambda x:seq[x])[0]),
    To=('label',lambda s:sorted(s,key=lambda x:seq[x])[-1]),Zone=('zone','first')).reset_index()
skc=inv[inv['To Rack']!='-'].groupby('To Category').agg(SKUs=('sku_id','nunique'),Moves=('Move?',lambda s:(s=='Yes').sum())).reset_index()
cp=cp.merge(skc,left_on='category',right_on='To Category',how='left').drop(columns='To Category')
cp['SKUs']=cp.SKUs.fillna(0).astype(int); cp['Moves']=cp.Moves.fillna(0).astype(int)
cp=cp.rename(columns={'category':'Unit (Category / Subcategory)'})[['Unit (Category / Subcategory)','Zone','SKUs','Racks','From','To','Moves']].sort_values(['Zone','From'])
cp.to_pickle('cp.pkl')
# 8-person balanced contiguous split by destination rack
m=inv[inv['To Rack']!='-'].copy(); m['seq']=m['To Rack'].map(seq)
w=m.groupby(['seq','To Rack']).size().reset_index(name='mv').sort_values('seq').reset_index(drop=True)
loads=w.mv.tolist(); n=len(loads); K=min(8,n); pre_=[0]
for x in loads: pre_.append(pre_[-1]+x)
seg=lambda a,bb:pre_[bb]-pre_[a]; INF=float('inf')
dp=[[INF]*(K+1) for _ in range(n+1)]; cut=[[0]*(K+1) for _ in range(n+1)]; dp[0][0]=0
for j in range(1,n+1):
    for k in range(1,K+1):
        for ii in range(j):
            v=max(dp[ii][k-1],seg(ii,j))
            if v<dp[j][k]: dp[j][k]=v; cut[j][k]=ii
bnd=[]; j=n; k=K
while k>0: ii=cut[j][k]; bnd.append((ii,j)); j=ii; k-=1
bnd=bnd[::-1]; r2p={}; rows=[]
for pi,(ii,j) in enumerate(bnd,1):
    c=w.iloc[ii:j]
    for l in c['To Rack']: r2p[l]=f'Person {pi}'
    rows.append(dict(Person=f'Person {pi}',From=c['To Rack'].iloc[0],To=c['To Rack'].iloc[-1],Racks=len(c),Moves=int(c.mv.sum())))
pd.DataFrame(rows).to_pickle('alloc.pkl')
inv['Assigned To']=inv['To Rack'].map(r2p); inv.to_pickle('packed.pkl')
# ---- workbook ----
cp=pd.read_pickle('cp.pkl'); rt=pd.read_pickle('racks_assigned.pkl').sort_values('seq'); inv=pd.read_pickle('packed.pkl'); alloc=pd.read_pickle('alloc.pkl')
HDR=PatternFill('solid',fgColor='1F3864'); HF=Font(name='Arial',bold=True,color='FFFFFF',size=10)
CF=Font(name='Arial',size=10); TF=Font(name='Arial',bold=True,size=13,color='1F3864')
th=Side(style='thin',color='D9D9D9'); BORD=Border(th,th,th,th)
CEN=Alignment('center','center'); LEF=Alignment('left','center',wrap_text=True)
ALT=PatternFill('solid',fgColor='F2F5FA'); MOVE=PatternFill('solid',fgColor='FFF2CC')
FOODF=PatternFill('solid',fgColor='E2EFDA'); NFOODF=PatternFill('solid',fgColor='FCE4D6'); SPAREF=PatternFill('solid',fgColor='EDEDED')
PAANF=PatternFill('solid',fgColor='C00000'); BTYF=PatternFill('solid',fgColor='F4B6C2'); XLF=PatternFill('solid',fgColor='BDD7EE'); OHF=PatternFill('solid',fgColor='D9D9D9')
PCOL=['E2EFDA','FCE4D6','DDEBF7','FFF2CC','EDEDED','E4DFEC','DEEAF6','FCE9DB']
wb=Workbook()
def sheet(name,df,title,widths,center=()):
    ws=wb.create_sheet(name); ws.sheet_view.showGridLines=False
    ws['A1']=title; ws['A1'].font=TF; ws.row_dimensions[1].height=22; hr=3
    for j,c in enumerate(df.columns,1):
        x=ws.cell(hr,j,c); x.fill=HDR; x.font=HF; x.alignment=CEN; x.border=BORD
    for r,(_,row) in enumerate(df.iterrows(),hr+1):
        for j,c in enumerate(df.columns,1):
            val=row[c]
            if isinstance(val,float) and np.isnan(val): val=None
            x=ws.cell(r,j,val); x.font=CF; x.border=BORD; x.alignment=CEN if c in center else LEF
            if (r-hr)%2==0: x.fill=ALT
    for col,w in widths.items(): ws.column_dimensions[col].width=w
    ws.freeze_panes=f'A{hr+1}'; return ws,hr

ws,hr=sheet('Category Plan',cp,'Floor 2 (Dry_2) Re-slot — volume-matched, food/non-food zoned',
  {'A':24,'B':10,'C':8,'D':7,'E':7,'F':7,'G':16,'H':8},center=list(cp.columns[1:]))
for r in range(hr+1,hr+1+len(cp)):
    ws.cell(r,2).fill=FOODF if ws.cell(r,2).value=='FOOD' else NFOODF

ra=rt[['seq','label','domtier','category','zone']].copy(); ra.columns=['Seq','Aisle-Rack','Bin Tier','Category','Zone']
ws,hr=sheet('Rack Layout',ra,'Floor 2 Rack -> Category (each rack single-category; food & non-food never share a rack)',
  {'A':6,'B':12,'C':9,'D':24,'E':10},center=['Seq','Aisle-Rack','Bin Tier','Zone'])
for r in range(hr+1,hr+1+len(ra)):
    z=ws.cell(r,5).value; cat=ws.cell(r,4).value
    fill=FOODF if z=='FOOD' else (NFOODF if z=='NON-FOOD' else SPAREF)
    for j in [1,2,3,4,5]: ws.cell(r,j).fill=fill
    if cat=='Paan Corner': ws.cell(r,4).fill=PAANF; ws.cell(r,4).font=Font(name='Arial',size=10,bold=True,color='FFFFFF')
    if cat=='Premium Beauty': ws.cell(r,4).fill=BTYF

al=alloc.rename(columns={'From':'Rack From','To':'Rack To'})
ws,hr=sheet('Person Allocation',al,f'Movement Split — {K} people, exclusive contiguous destination racks',
  {'A':12,'B':11,'C':11,'D':8,'E':9},center=['Rack From','Rack To','Racks','Moves'])
for r in range(hr+1,hr+1+len(al)):
    for j in range(1,6): ws.cell(r,j).fill=PatternFill('solid',fgColor=PCOL[(r-hr-1)%len(PCOL)])

mv=inv.rename(columns={'sku_id':'SKU ID','product_name':'SKU Name','category_name':'Old Category','To Category':'New Category',
  'sku_vol_cc':'SKU Vol cc','size':'Size','bin_code':'From Bin','live_inv_qty':'Qty'})
mv=mv[['SKU ID','SKU Name','Old Category','New Category','SKU Vol cc','Size','From Bin','To Bin','To Bin Class','To Rack','Qty','Move?','Rule','Assigned To']].sort_values(['Assigned To','To Rack','To Bin','SKU Name'])
mv['SKU Vol cc']=mv['SKU Vol cc'].fillna(0).round(0).astype(int)
ws,hr=sheet('Bin-to-Bin Moves',mv,'Floor 2 SKU Relocation — volume-matched, comingle-safe, Paan@J1/J3, HVP/beauty/liquid off deep&overhead',
  {'A':30,'B':42,'C':18,'D':18,'E':9,'F':7,'G':14,'H':14,'I':10,'J':8,'K':6,'L':7,'M':30,'N':11},
  center=['SKU Vol cc','Size','From Bin','To Bin','To Bin Class','To Rack','Qty','Move?','Assigned To'])
pm={f'Person {k+1}':PCOL[k%len(PCOL)] for k in range(K)}
ci={c:list(mv.columns).index(c)+1 for c in ['To Bin Class','Move?','Assigned To','Rule']}
for r in range(hr+1,hr+1+len(mv)):
    ws.cell(r,ci['Assigned To']).fill=PatternFill('solid',fgColor=pm.get(ws.cell(r,ci['Assigned To']).value,'FFFFFF'))
    if ws.cell(r,ci['Move?']).value=='Yes': ws.cell(r,ci['Move?']).fill=MOVE
    bc=ws.cell(r,ci['To Bin Class']).value
    if bc=='XL': ws.cell(r,ci['To Bin Class']).fill=XLF
    elif bc=='BEAUTY': ws.cell(r,ci['To Bin Class']).fill=BTYF
    elif bc in ('OVERHEAD','RESERVE'): ws.cell(r,ci['To Bin Class']).fill=OHF
    if str(ws.cell(r,ci['Rule']).value).startswith('Paan'):
        c=ws.cell(r,ci['Rule']); c.fill=PAANF; c.font=Font(name='Arial',size=10,bold=True,color='FFFFFF')

nmoves=int((inv['Move?']=='Yes').sum()); mh=nmoves*15/3600
leg=wb.create_sheet('Read Me'); leg.sheet_view.showGridLines=False
N=[('Floor 2 (Dry_2) Consolidated Re-slot — volumetric','T'),('',''),
('Built from REAL volumetrics','H'),
('Uses sku_vol_cc (actual per-unit SKU volume) vs btc_vol_cc (bin volume capacity) — no pack-size guessing.',''),
('Each SKU placed in a bin whose volume fits it: small SKUs -> D_140H/D_BEAUTY cells, medium -> D_300L/D_400D, large -> D_600D/D_LSS.',''),
('Bin volumes: D_BEAUTY 3,168cc | D_140H 6,337cc | D_300L ~20k | D_400D ~23-29k | D_600D ~34-43k | D_LSS 60,480cc | Deep(overhead) 1.44M cc.',''),
('',''),
('Hard rules (all verified)','H'),
('Food and non-food never share a rack — every rack is single-category. Zone column marks each.',''),
('No bin exceeds its comingle limit. 0 medium/large SKUs forced into D_140H small cells.',''),
('Entire Paan Corner (cigarettes + smoking accessories, HVP) -> J-1 & J-3 only; never overhead/reserve.',''),
('Premium beauty (Makeup, Skincare, Fragrances) -> D_BEAUTY panda racks L-14/16/18; never overhead/reserve.',''),
('Liquids -> never in overhead (space above rack) or deep-reserve (D_600D) bins.',''),
('D_BAT bins (J-4/J-6) -> long-handle articles only: mops, brooms, wipers, squeegees, floor scrubbers.',''),
('High-volume subcategories (>=150 SKUs) get dedicated racks within their category block.',''),
('D_LSS rack N-5 = shared XL pool for oversized SKUs (big buckets, 5kg pet food, bulk mops) that exceed normal bin volume.',''),
('Deep (1/rack) = overhead space above rack = reserve only, used last for same-category bulky top-up.',''),
('',''),
('Movement','H'),
(f'{nmoves:,} moves, {K} people on exclusive contiguous destination racks. ~{mh:.0f} man-hours @15s/move; parallel finish ~{mh/max(K,1):.1f} h.',''),
('',''),
('Sheets','H'),
('Category Plan | Rack Layout (food green / non-food orange / Paan red / beauty pink) | Person Allocation | Bin-to-Bin Moves.',''),
('Moves sheet: SKU Vol cc + Size + To Bin Class show the volume match; Rule explains each placement; Assigned To colour-coded.','')]
leg['A1']=N[0][0]; leg['A1'].font=TF
for k,(t,ty) in enumerate(N[1:],2):
    c=leg.cell(k,1,t); c.font=Font(name='Arial',bold=True,size=11,color='1F3864') if ty=='H' else Font(name='Arial',size=10)
leg.column_dimensions['A'].width=128
wb.remove(wb['Sheet']); wb._sheets=[wb['Read Me'],wb['Category Plan'],wb['Rack Layout'],wb['Person Allocation'],wb['Bin-to-Bin Moves']]
out=os.environ.get('RESLOT_OUT','/mnt/user-data/outputs/Floor2_Reslot_Volumetric.xlsx')
os.makedirs(os.path.dirname(os.path.abspath(out)),exist_ok=True)
wb.save(out); print('saved',out,'| moves:',nmoves)
