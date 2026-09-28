from __future__ import annotations

import ast
import functools
import hashlib
import inspect
import math
import textwrap
from contextlib import contextmanager


GATE_NAME = "__history_xgb_runtime_gate__"


def make_decider(feature_builder, predictor):
    records = []

    def decide(self):
        if not self.entry_candidate_snapshots:
            raise RuntimeError("runtime_candidate_snapshot_missing")
        row = self.entry_candidate_snapshots[-1]
        if row["product_vt_symbol"] == "fu.SHFE":
            return False
        if (row["entry_context"] != "flat_entry" or row["candidate_status"] != "opened"
                or row["is_opened"] != 1):
            raise RuntimeError("runtime_candidate_not_opened_root")
        event = feature_builder(dict(row))
        prediction = predictor(event)
        skip = prediction["skip"]
        if not isinstance(skip, bool):
            raise RuntimeError("runtime_prediction_action_mismatch")
        ret, dd = prediction["return_marginal"], prediction["drawdown_marginal"]
        if prediction["status"] == "untrained":
            valid = not skip and ret is None and dd is None
        elif prediction["status"] == "predicted":
            valid = (isinstance(ret, (int, float)) and isinstance(dd, (int, float))
                     and math.isfinite(ret) and math.isfinite(dd) and skip == (ret < 0 and dd < 0))
        else:
            valid = False
        if not valid:
            raise RuntimeError("runtime_prediction_action_mismatch")
        records.append({**event, **prediction})
        if skip:
            row.update(candidate_status="skipped", skip_reason="research_xgb_predicted_harm", is_opened=0)
        return skip

    return decide, records


def instrument_source(source, method_only=True):
    parsed = ast.parse(textwrap.dedent(source))
    methods = [node for node in ast.walk(parsed) if isinstance(node, ast.FunctionDef) and node.name == "on_bars"]
    if len(methods) != 1 or (method_only and len(parsed.body) != 1):
        raise RuntimeError("runtime_gate_shape_changed")
    method = methods[0]
    if method.decorator_list:
        raise RuntimeError("runtime_gate_shape_changed")
    expected = ast.dump(ast.parse('if candidate_status != "opened":\n    continue').body[0], include_attributes=False)
    sites = []
    for parent in ast.walk(method):
        for _, items in ast.iter_fields(parent):
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if (isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                        and isinstance(item.value.func, ast.Attribute)
                        and item.value.func.attr == "_record_entry_candidate_snapshot"):
                    if (index + 1 >= len(items)
                            or ast.dump(items[index + 1], include_attributes=False) != expected):
                        raise RuntimeError("runtime_gate_shape_changed")
                    sites.append((items, index))
    if len(sites) != 1:
        raise RuntimeError("runtime_gate_shape_changed")
    items, index = sites[0]
    gate = ast.parse(f'if candidate_status == "opened" and {GATE_NAME}(self):\n    continue').body[0]
    items.insert(index + 1, gate)
    return ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))


@contextmanager
def install_gate(strategy_class, decide):
    original = strategy_class.on_bars
    namespace = original.__globals__
    if GATE_NAME in namespace:
        raise RuntimeError("runtime_gate_already_installed")
    if original.__closure__:
        raise RuntimeError("runtime_gate_closure_unsupported")
    source = textwrap.dedent(inspect.getsource(original))
    tree = instrument_source(source)
    audit = {"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "gate_call_count": 0, "skip_count": 0}
    missing = object()
    old_local = strategy_class.__dict__.get("on_bars", missing)
    installed = False

    def gate(self):
        audit["gate_call_count"] += 1
        skip = decide(self)
        if not isinstance(skip, bool):
            raise RuntimeError("runtime_gate_decision_not_boolean")
        audit["skip_count"] += int(skip)
        return skip

    namespace[GATE_NAME] = gate
    try:
        local = {}
        exec(compile(tree, original.__code__.co_filename + "::research_xgb_gate", "exec"), namespace, local)
        replacement = functools.update_wrapper(local["on_bars"], original)
        setattr(strategy_class, "on_bars", replacement)
        installed = True
        yield audit
    finally:
        if installed:
            if old_local is missing:
                delattr(strategy_class, "on_bars")
            else:
                setattr(strategy_class, "on_bars", old_local)
        del namespace[GATE_NAME]
