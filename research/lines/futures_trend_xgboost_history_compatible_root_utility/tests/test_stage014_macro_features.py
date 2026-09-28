import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage014_macro_features.py"
    assert path.exists(), "macro feature implementation missing"
    spec = importlib.util.spec_from_file_location("macro_feature_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def returns():
    days = pd.bdate_range("2024-01-02", periods=150).strftime("%Y-%m-%d")
    return pd.DataFrame([{"date": day, "root": root, "product_return": np.sin(i / 7 + offset) / 100}
                         for i, day in enumerate(days) for offset, root in enumerate(("IF", "IH", "IC", "T", "TF", "TS"))])


def test_fixed_formulas_use_equal_weighted_same_contract_returns():
    m = module()
    data = returns()
    got = m.daily_factors(data).iloc[-1]
    wide = data.pivot(index="date", columns="root", values="product_return")
    e = wide[["IF", "IH", "IC"]].mean(axis=1)
    b = wide[["T", "TF", "TS"]].mean(axis=1)
    assert got.cffex_equity_momentum_20d == pytest.approx(np.prod(1 + e.iloc[-20:]) - 1)
    assert got.cffex_rates_momentum_20d == pytest.approx(np.prod(1 + b.iloc[-20:]) - 1)
    assert got.cffex_equity_vol_ratio_20_120 == pytest.approx(e.iloc[-20:].std() / e.iloc[-120:].std())
    assert got.cffex_rates_vol_ratio_20_120 == pytest.approx(b.iloc[-20:].std() / b.iloc[-120:].std())
    assert got.cffex_equity_rates_corr_60d == pytest.approx(e.iloc[-60:].corr(b.iloc[-60:]))


def context():
    m = module()
    factors = m.daily_factors(returns())
    days = factors.date.tolist()
    mapping = pd.DataFrame({"decision_date": days[120:], "source_date": days[119:-1], "coverage_status": "available"})
    return m, m.decision_context(factors, mapping)


def test_direction_flips_only_momentum_and_missing_decision_never_falls_back():
    m, data = context()
    day = data.decision_date.iloc[-1]
    long = m.features_for_decision(data, day, "long")
    short = m.features_for_decision(data, day, "short")
    assert len(long) == len(short) == 5
    for name in m.FEATURES[:2]:
        assert long[name] == -short[name]
    for name in m.FEATURES[2:]:
        assert long[name] == short[name]
    with pytest.raises(RuntimeError, match="direction"):
        m.features_for_decision(data, day, "unknown")
    with pytest.raises(RuntimeError, match="decision"):
        m.features_for_decision(data, "2050-01-01", "long")


def test_same_day_and_future_changes_do_not_affect_past_decision():
    m = module()
    data = returns()
    days = sorted(data.date.unique())
    mapping = pd.DataFrame({"decision_date": [days[130]], "source_date": [days[129]], "coverage_status": ["available"]})
    first = m.decision_context(m.daily_factors(data), mapping)
    data.loc[data.date.ge(days[130]), "product_return"] += 0.5
    second = m.decision_context(m.daily_factors(data), mapping)
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    mapping["source_date"] = mapping.decision_date
    with pytest.raises(RuntimeError, match="prior"):
        m.decision_context(m.daily_factors(data), mapping)


def test_missing_roots_duplicates_and_zero_variance_do_not_get_imputed():
    m = module()
    data = returns()
    with pytest.raises(RuntimeError, match="root"):
        m.daily_factors(data.loc[data.root.ne("TS")])
    with pytest.raises(RuntimeError, match="duplicate"):
        m.daily_factors(pd.concat([data, data.iloc[:1]]))
    data["product_return"] = 0.0
    factors = m.daily_factors(data)
    assert pd.isna(factors.cffex_equity_vol_ratio_20_120.iloc[-1])
    mapping = pd.DataFrame({"decision_date": ["2025-01-01"], "source_date": [factors.date.iloc[-1]], "coverage_status": ["available"]})
    with pytest.raises(RuntimeError, match="nonfinite"):
        m.decision_context(factors, mapping)


def test_candidate_spec_only_adds_five_features_not_parameters_or_actions():
    m = module()
    original = {"features": ["old"], "estimator": {"max_depth": 2}, "action": "dual_negative"}
    result = m.candidate_spec(original)
    assert result["features"] == ["old", *m.FEATURES]
    assert {k: v for k, v in result.items() if k != "features"} == {k: v for k, v in original.items() if k != "features"}
    assert original["features"] == ["old"]


def test_output_exists_before_source_read(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    with pytest.raises(RuntimeError, match="already_exists"):
        m.run()
