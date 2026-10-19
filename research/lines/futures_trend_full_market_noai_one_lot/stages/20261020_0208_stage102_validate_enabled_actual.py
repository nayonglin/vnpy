"""Reproduce only enabled v1 display measurements; no paired/agent-review claim."""
import argparse,hashlib,json,sys
from pathlib import Path
line=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(line/'tools'))
import stage097_validate_quarter_display as audit

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 source=line/'outputs/run_20261020_risk025_contract_weekly_v1';prefix=line/'outputs/recap_20261020_risk025_contract_weekly_v1';review=line/'stages/20261020_0203_stage101_risk025_weekly_enabled_actual_review.json';review_sha=hashlib.sha256(review.read_bytes()).hexdigest();metadata=json.loads(review.read_text())
 assert review_sha=='3a0ba1efa4d54e887dc7862ee4be48baab0dfafd3b38952ceb0b2de29f7f950e'
 assert metadata['verdict']=='PASS_WITH_LIMITS' and metadata['source_manifest_sha256']=='7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35'
 audit.source_mode(source,True);namespace,proof=audit.audit_namespace();result=namespace['validate'](source,line/'outputs/run_20261019_contract_weekly_long_v1',Path(str(prefix)+'_raw'),Path(str(prefix)+'_fractional'),Path(str(prefix)+'_weekly'),Path(str(prefix)+'_reviewed_v2'))
 result.update(stage='Stage102',status='PASS_ENABLED_V1_DISPLAY_VALIDATION_ONLY',scope='enabled_v1_raw_fractional_weekly_final',risk_fraction=.0025,pair_validation=False,off_financial_run_status='failed_no_complete_manifest_not_visualized',independent_agent_review=False,validation_executed_by='display implementation author using separate calculation code',actual_financial_review=dict(path=str(review),sha256=review_sha,verdict=metadata['verdict']),independent_algorithm_reuse=proof,caller_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 for protected in (source,line/'outputs/run_20261019_contract_weekly_long_v1',*[Path(str(prefix)+s) for s in ('_raw','_fractional','_weekly','_reviewed_v2')]):
  if a.output.resolve().is_relative_to(protected.resolve()):raise ValueError('report_inside_frozen_input')
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('status','complete_entries','complete_contracts','residual_entries','residual_contracts','exact_weekly','pair_validation')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
