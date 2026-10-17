"""Stage073 bounded review probes; no data replay, model use or source mutation."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
LINE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(LINE / "tools"))
import stage065_pairwise_off_policy as policy

stdlib_only = not any(name in sys.modules for name in ("numpy", "pandas", "sklearn", "joblib"))
assert stdlib_only
import stage022_run_c0_qualified_wait as runtime

results = []
calls = dict(load=0, runtime=0, score=0, predict=0, fit=0, old_smoke=0)
def forbidden(name):
    def fail(*args, **kwargs):
        calls[name] += 1
        raise AssertionError("forbidden_model_path:" + name)
    return fail

with tempfile.TemporaryDirectory(prefix="stage073_probes_") as temp:
    runtime.OUTPUT = Path(temp) / "runtime"
    runtime.configure_runtime(Path(temp) / "shared")
    import joblib
    import qmt_roll_ai_selection_pairwise_runtime as pairwise
    from sklearn.pipeline import Pipeline
    with ExitStack() as stack:
        stack.enter_context(patch.object(joblib, "load", forbidden("load")))
        stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel, "__init__", forbidden("runtime")))
        stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel, "score_candidate_pool", forbidden("score")))
        for name in ("predict", "predict_proba"):
            stack.enter_context(patch.object(Pipeline, name, forbidden("predict")))
        stack.enter_context(patch.object(Pipeline, "fit", forbidden("fit")))
        stack.enter_context(patch.object(runtime, "model_runtime_smoke", forbidden("old_smoke")))
        evidence = json.loads((OUT / "test1.json").read_text())
        for case in evidence["cases"]:
            requested = case["fixture_requested"]
            actual = case["fixture_actual"]
            reference = deepcopy(requested)
            for key, value in case["delta"]["changes"].items():
                reference[key] = value["reference"]
            for key in case["delta"]["declared_defaults_used"]:
                reference.pop(key, None)
            kwargs = dict(shared=Path(temp) / "shared", reference_shared=Path(temp) / "shared")
            assert policy.check_settings_delta(reference, requested, actual, **kwargs)["actual_settings_match_off_expected"]
            for side in ("requested", "actual"):
                for key, value in (("account_capital", 150001.0), ("c3_capital", 150001.0),
                                   ("risk_ratio_of_total_assets", .777),
                                   ("ai_product_pool_eligibility_path", "/tmp/stage073-unexpected-pool"),
                                   ("unknown_non_policy_path", "/tmp/stage073-extra")):
                    bad_requested, bad_actual = deepcopy(requested), deepcopy(actual)
                    (bad_requested if side == "requested" else bad_actual)[key] = value
                    try:
                        policy.check_settings_delta(reference, bad_requested, bad_actual, **kwargs)
                    except ValueError as error:
                        results.append(dict(arm=case["arm"], probe=side + "_drift", field=key, rejected=str(error)))
                    else:
                        raise AssertionError("non_policy_drift_accepted:" + side + ":" + key)
                for key in (*policy.OFF_SETTINGS, "account_capital", "c3_capital", "risk_ratio_of_total_assets"):
                    bad_requested, bad_actual = deepcopy(requested), deepcopy(actual)
                    del (bad_requested if side == "requested" else bad_actual)[key]
                    try:
                        policy.check_settings_delta(reference, bad_requested, bad_actual, **kwargs)
                    except ValueError as error:
                        results.append(dict(arm=case["arm"], probe=side + "_missing", field=key, rejected=str(error)))
                    else:
                        raise AssertionError("missing_field_accepted:" + side + ":" + key)
            effective = case["effective"]["effective"]
            assert policy.check_effective_off_policy(SimpleNamespace(**effective))["status"] == "passed_effective_pairwise_off"
            bad_values = {key: (True if isinstance(value, bool) else 1) for key, value in policy.OFF_SETTINGS.items()}
            bad_values.update(selection_pairwise_runtime=object(), ai_path_damage_runtime=object(),
                              enable_ai_path_damage_risk_discount=True, stage827_require_complete_minutes=False)
            for key, value in bad_values.items():
                try:
                    policy.check_effective_off_policy(SimpleNamespace(**{**effective, key: value}))
                except ValueError as error:
                    results.append(dict(arm=case["arm"], probe="effective_attribute_drift", field=key, rejected=str(error)))
                else:
                    raise AssertionError("effective_drift_accepted:" + key)

assert not any(calls.values())
receipt = dict(schema="stage073_small_counterexamples_v1", command=".py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage073_pairwise_off_policy_independent_review/small_counterexamples.py",
               exit_code=0, stdlib_import_only=stdlib_only, source_sha256=hashlib.sha256((LINE/"tools/stage065_pairwise_off_policy.py").read_bytes()).hexdigest(),
               rejection_count=len(results), probes=results, model_spies=calls, financial_replays=0, production_qualified=False)
(OUT/"small_counterexamples.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: value for key, value in receipt.items() if key != "probes"}, ensure_ascii=False, indent=2))
