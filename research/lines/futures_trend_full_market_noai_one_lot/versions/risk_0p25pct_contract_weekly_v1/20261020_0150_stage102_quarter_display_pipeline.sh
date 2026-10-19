#!/bin/bash
# Display only. initial: 2+2 context workers; final: actual reviews required;
# validate: generator's full readonly numeric/artifact audit, not independent-agent review.
set -euo pipefail
display_line=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
display_repo=$(cd "$display_line/../../.." && pwd)
display_py=/Users/mac/Desktop/fian/.py311/bin/python
display_tools="$display_line/tools"
cd "$display_repo"
display_on_source="$display_line/outputs/run_20261020_risk025_contract_weekly_v1"
display_off_source="$display_line/outputs/run_20261020_risk025_no_weekly_v1"
display_on="$display_line/outputs/recap_20261020_risk025_contract_weekly_v1"
display_off="$display_line/outputs/recap_20261020_risk025_no_weekly_v1"
display_overview="$display_line/outputs/overview_20261020_risk025_pair_v1"
display_phase=${1:-}
# Fail before any rendering if the frozen display source or original full-suite log changed.
"$display_py" - "$display_line" <<'PY'
import sys,hashlib
from pathlib import Path
line=Path(sys.argv[1]);expected={'tools/stage094_quarter_risk_recap.py':'d57815e4e8df26b0390c0f54fe7d687e23502f1fc7e82fe48fd49ae1f9675b04','tools/stage095_quarter_weekly_display.py':'a1d77563c8576c3b03f841ff6c78f0775340df953bd3ee627d5cd47f958391e5','tools/stage096_quarter_pair_overview.py':'ef3c4db803e97320e99b181d8bf61ae1af688f336db9bc2f48419d8c058cb552','tools/stage097_validate_quarter_display.py':'f31fc85b5f82eef83905b92df94df5ef78fe117b686d4562680f336f6a6c45b7','stages/20261020_0147_stage094_097_stable_full_suite.log':'7e396fb5949b02813c288e378d550a061baa0ad3253e0b32d7ab38e736ad450a'}
for name,digest in expected.items():
 if hashlib.sha256((line/name).read_bytes()).hexdigest()!=digest:raise SystemExit('frozen display dependency changed: '+name)
PY
case "$display_phase" in
 initial)
  # Only after root confirms both complete manifests; never run against protocol/prefix.
  "$display_py" - "$display_tools" "$display_on_source" "$display_off_source" <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from stage094_quarter_risk_recap import validate_policy
from stage042_account_overview import verify_hashes
for value in sys.argv[2:]:
 root=Path(value);m=json.loads((root/'manifest.json').read_text());s=json.loads((root/'summary.json').read_text());validate_policy(m,s);verify_hashes(root,m)
 if m['run_id']!=root.name or (root/'failure_snapshot.json').exists() or s.get('performance_certifiable') is not True:raise SystemExit('source not complete: '+value)
PY
  "$display_py" "$display_tools/stage025_parallel_context_recap.py" --source "$display_on_source" --output "${display_on}_raw" --workers 2 > /tmp/risk025_contract_weekly_raw.log 2>&1 &
  display_on_pid=$!
  "$display_py" "$display_tools/stage025_parallel_context_recap.py" --source "$display_off_source" --output "${display_off}_raw" --workers 2 > /tmp/risk025_no_weekly_raw.log 2>&1 &
  display_off_pid=$!
  display_on_status=0;display_off_status=0
  wait "$display_on_pid" || display_on_status=$?
  wait "$display_off_pid" || display_off_status=$?
  if (( display_on_status != 0 || display_off_status != 0 )); then
   echo "raw display failed: enabled=$display_on_status disabled=$display_off_status" >&2
   exit 1
  fi
  # Serialize cache-heavy enrichments after both raw processes have exited.
  "$display_py" "$display_tools/stage094_quarter_risk_recap.py" --source "$display_on_source" --parent "${display_on}_raw" --output "${display_on}_fractional" > /tmp/risk025_contract_weekly_fractional.log 2>&1
  "$display_py" "$display_tools/stage095_quarter_weekly_display.py" --source "$display_on_source" --parent "${display_on}_fractional" --output "${display_on}_weekly" > /tmp/risk025_contract_weekly_weekly.log 2>&1
  "$display_py" "$display_tools/stage094_quarter_risk_recap.py" --source "$display_off_source" --parent "${display_off}_raw" --output "${display_off}_fractional" > /tmp/risk025_no_weekly_fractional.log 2>&1
  "$display_py" "$display_tools/stage095_quarter_weekly_display.py" --source "$display_off_source" --parent "${display_off}_fractional" --output "${display_off}_weekly" > /tmp/risk025_no_weekly_weekly.log 2>&1
  ;;
 final)
  if [[ $# != 3 ]]; then echo 'final requires enabled_actual_PASS.md and disabled_actual_PASS.md' >&2;exit 2;fi
  display_on_review=$2;display_off_review=$3
  # Actual source-bound review metadata only. Preflight is never accepted here.
  "$display_py" - "$display_on_source" "$display_on_review" "$display_off_source" "$display_off_review" <<'PY'
import sys,json,hashlib
from pathlib import Path
for source,review in ((sys.argv[1],sys.argv[2]),(sys.argv[3],sys.argv[4])):
 source=Path(source);review=Path(review)
 if 'preflight' in review.name.lower():raise SystemExit('preflight cannot authorize final display')
 metadata=review if review.suffix=='.json' else review.with_suffix('.json');r=json.loads(metadata.read_text());actual=hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest()
 if r.get('source_manifest_sha256')!=actual or r.get('verdict') not in ('PASS','PASS_WITH_LIMITS'):raise SystemExit('actual financial PASS/source binding absent: '+str(review))
PY
  "$display_py" "$display_tools/stage020_review_finalizer.py" "${display_on}_weekly" "$display_on_review" "${display_on}_reviewed" > /tmp/risk025_contract_weekly_reviewed.log 2>&1
  "$display_py" "$display_tools/stage083_final_multilot_labels.py" --parent "${display_on}_reviewed" --output "${display_on}_labels" > /tmp/risk025_contract_weekly_labels.log 2>&1
  "$display_py" "$display_tools/stage067_current_trade_reset.py" --parent "${display_on}_labels" --output "${display_on}_reviewed_v2" > /tmp/risk025_contract_weekly_reset.log 2>&1
  "$display_py" "$display_tools/stage020_review_finalizer.py" "${display_off}_weekly" "$display_off_review" "${display_off}_reviewed" > /tmp/risk025_no_weekly_reviewed.log 2>&1
  "$display_py" "$display_tools/stage083_final_multilot_labels.py" --parent "${display_off}_reviewed" --output "${display_off}_labels" > /tmp/risk025_no_weekly_labels.log 2>&1
  "$display_py" "$display_tools/stage067_current_trade_reset.py" --parent "${display_off}_labels" --output "${display_off}_reviewed_v2" > /tmp/risk025_no_weekly_reset.log 2>&1
  "$display_py" "$display_tools/stage096_quarter_pair_overview.py" --enabled-source "$display_on_source" --disabled-source "$display_off_source" --enabled-recap "${display_on}_reviewed_v2" --disabled-recap "${display_off}_reviewed_v2" --output "$display_overview" > /tmp/risk025_pair_overview.log 2>&1
  ;;
 validate)
  "$display_py" "$display_tools/stage097_validate_quarter_display.py" --enabled-source "$display_on_source" --disabled-source "$display_off_source" --data-source "$display_line/outputs/run_20261019_contract_weekly_long_v1" --enabled-raw "${display_on}_raw" --disabled-raw "${display_off}_raw" --enabled-fractional "${display_on}_fractional" --disabled-fractional "${display_off}_fractional" --enabled-weekly "${display_on}_weekly" --disabled-weekly "${display_off}_weekly" --enabled-final "${display_on}_reviewed_v2" --disabled-final "${display_off}_reviewed_v2" --overview "$display_overview" --output "$display_line/stages/stage102_validate_quarter_display.json" > /tmp/risk025_pair_actual_validation.log 2>&1
  ;;
 *) echo 'usage: bash pipeline.sh initial | final enabled_actual_PASS.md disabled_actual_PASS.md | validate' >&2;exit 2;;
esac
