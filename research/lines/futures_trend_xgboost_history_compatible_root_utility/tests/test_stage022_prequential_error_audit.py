import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage022_prequential_error_audit.py"
    assert path.exists(), "prequential error audit implementation missing"
    spec = importlib.util.spec_from_file_location("stage022_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def row(i, **changes):
    value = dict(event_id=str(i), decision_date="2021-01-02", cutoff="2021-01-01",
                 label_end_date="2021-01-31", label_status="verified", status="predicted",
                 skip=True, return_marginal=-0.1, drawdown_marginal=-0.1,
                 pred_return_marginal=-0.2, pred_drawdown_marginal=-0.2)
    value.update(changes)
    return value


def test_order_statistic_requires_39_and_has_no_interpolation():
    m = module()
    assert m.upper_error(list(range(38))) is None
    assert m.upper_error(list(range(39))) == 38
    assert m.upper_error(list(range(40))) == 39
    assert m.upper_error(list(range(79))) == 77


def test_strict_label_maturity_excludes_cutoff_and_censored_and_untrained():
    m = module()
    history = [row(i) for i in range(39)]
    history += [row("cutoff", label_end_date="2021-02-01"),
                row("censored", label_status="censored", label_end_date="",
                    return_marginal=None, drawdown_marginal=None),
                row("untrained", status="untrained", skip=False,
                    pred_return_marginal=None, pred_drawdown_marginal=None)]
    result = m.audit(history + [row("current", decision_date="2021-02-02", cutoff="2021-02-01",
                                   label_end_date="2021-02-03")], ["2021-02-01"])
    month = result["months"][0]
    assert month["reference_count"] == 39
    assert set(month["reference_event_ids"]) == {str(i) for i in range(39)}
    current = next(r for r in result["events"] if r["event_id"] == "current")
    assert current["supported_veto"] is True


def test_current_and_later_labels_cannot_change_current_bound():
    m = module()
    data = [row(i) for i in range(39)]
    data += [row("current", decision_date="2021-02-02", cutoff="2021-02-01", label_end_date="2021-03-01"),
             row("later", decision_date="2021-03-02", cutoff="2021-03-01", label_end_date="2021-03-03")]
    changed = copy.deepcopy(data)
    for r in changed[-2:]:
        r.update(return_marginal=10000.0, drawdown_marginal=10000.0)
    a, b = (m.audit(d, ["2021-02-01"])["events"] for d in (data, changed))
    assert a == b


def test_both_heads_strict_negative_and_point_veto_required():
    m = module()
    history = [row(i, return_marginal=-0.1, drawdown_marginal=-0.1) for i in range(39)]
    a = row("zero", decision_date="2021-02-02", cutoff="2021-02-01", label_end_date="2021-02-03",
            pred_drawdown_marginal=-0.1)
    b = row("positive", decision_date="2021-02-02", cutoff="2021-02-01", label_end_date="2021-02-03",
            pred_return_marginal=0.1, skip=False)
    result = m.audit(history + [a, b], ["2021-02-01"])
    assert not any(r["supported_veto"] for r in result["events"])


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "censored_value", "untrained_score", "month", "end", "action"])
def test_invalid_inputs_fail_explicitly(mutation):
    m = module()
    data = [row(1), row(2)]
    if mutation == "duplicate":
        data[1]["event_id"] = "1"
    elif mutation == "nan":
        data[0]["return_marginal"] = float("nan")
    elif mutation == "censored_value":
        data[0]["label_status"] = "censored"
    elif mutation == "untrained_score":
        data[0]["status"] = "untrained"
    elif mutation == "month":
        data[0]["cutoff"] = "2020-12-01"
    elif mutation == "end":
        data[0]["label_end_date"] = "2020-12-31"
    else:
        data[0]["skip"] = False
    with pytest.raises(ValueError):
        m.audit(data, ["2021-02-01"])
