"""Data-only: old119 raws already supplied by frozen full91 catalog; derive new planned/actual missing-request raws only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import stage008_snapshot_anchors_fast as harvest
if __name__=='__main__':
    harvest.PATTERNS=['stage008_minute_patches/planned*/*_proof.json','stage008_minute_patches/from_G*/*_proof.json']
    harvest.main()
