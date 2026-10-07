#!/usr/bin/env python3
"""
Floor-2 (Dry_2) warehouse re-slot pipeline — orchestrator.
Runs: engine -> allocate -> pack -> (person split + workbook via build) end to end.

Usage:
    python3 run_all.py \
        --bins   path/to/BIN_DOWNLOAD_*.csv \
        --inv    path/to/sqllab_*utilization*.csv \
        --out    path/to/Floor2_Reslot_Volumetric.xlsx

If no args are given it falls back to the default upload paths used during development.
Each stage writes intermediate .pkl files into the working dir; they are reused downstream.
"""
import argparse, subprocess, sys, os, pathlib
HERE=pathlib.Path(__file__).parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bins', default='/mnt/user-data/uploads/BIN_DOWNLOAD_BIN_DOWNLOAD_2026-10-06T09-47-23_256706_6C6BD.csv')
    ap.add_argument('--inv',  default='/mnt/user-data/uploads/sqllab_untitled_query_134_20261006T094554.csv')
    ap.add_argument('--wms',  default='', help='optional WMS INVENTORY_BY_SKU_BIN_LPN download; only stock in its Good bins is planned')
    ap.add_argument('--out',  default='/mnt/user-data/outputs/Floor2_Reslot_Volumetric.xlsx')
    a=ap.parse_args()
    # stages run with cwd=HERE, so resolve user paths against the caller's cwd first
    os.environ['RESLOT_BINS']=os.path.abspath(a.bins); os.environ['RESLOT_INV']=os.path.abspath(a.inv); os.environ['RESLOT_OUT']=os.path.abspath(a.out)
    if a.wms: os.environ['RESLOT_WMS']=os.path.abspath(a.wms)
    def run(stage):
        print(f'=== {stage} ===')
        r=subprocess.run([sys.executable, str(HERE/stage)], cwd=HERE)
        if r.returncode!=0: sys.exit(f'FAILED at {stage}')
    run('engine.py')
    run('allocate.py'); run('pack.py')
    run('build.py')
    print('DONE ->', os.environ['RESLOT_OUT'])

if __name__=='__main__': main()
