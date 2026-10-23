"""All AI selection off: add a fail-closed gate to frozen Stage011 reporting.

Only declared ledger/proof JSON is read. No model, feature CSV, minute evidence,
strategy constructor or financial replay is invoked. Artifact paths and final
review schema remain Stage011; its source bytes are never changed. Temporary
Stage011 bindings are always restored, including when validation raises.
"""
from contextlib import contextmanager
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import stage011_build_artifacts as base

AI_FLAGS=(
    'enable_selection_pairwise_v2',
    'enable_selection_pairwise_v2_catastrophic_veto',
    'enable_selection_pairwise_v2_catastrophic_hard_filter',
    'enable_selection_pairwise_v2_volume_tilt',
)
_ORIGINAL_LOAD_LEDGER=base.load_ledger


@contextmanager
def reporting_context():
    previous_flags,previous_loader=base.FLAGS,base.load_ledger
    try:
        base.FLAGS=list(dict.fromkeys([*previous_flags,*AI_FLAGS]))
        base.load_ledger=load_ledger
        yield
    finally:
        base.FLAGS=previous_flags
        base.load_ledger=previous_loader


def load_ledger(path,arm,products,calendar=None):
    with reporting_context():
        ledger=_ORIGINAL_LOAD_LEDGER(path,arm,products,calendar)
        proof_path=Path(path).resolve()/'ai_selection_acceptance.json'
        proof=json.loads(proof_path.read_text())
        valid=(proof.get('schema')=='stage012_ai_selection_off_v1'
            and proof.get('accepted') is True
            and proof.get('model_load_attempts')==0
            and proof.get('runtime_loaded') is False
            and proof.get('nonzero_ai_candidate_fields')==0)
        if not valid:raise ValueError('AI_selection_off_acceptance_required:'+arm)
        ledger['sources'][str(proof_path)]=base.sha(proof_path)
        ledger['sources'][str(Path(__file__).resolve())]=base.sha(__file__)
        ledger['ai_selection_acceptance']=proof
        return ledger


def build_artifacts(line_dir,review_json=None):
    with reporting_context():
        return base.build_artifacts(line_dir,review_json)


def main():
    with reporting_context():
        return base.main()

if __name__=='__main__':main()
