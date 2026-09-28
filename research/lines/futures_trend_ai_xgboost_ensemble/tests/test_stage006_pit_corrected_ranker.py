from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage006_pit_corrected_ranker.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage006_pit_corrected_ranker", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_future_label_end_is_last_product_trading_day_in_forward_path() -> None:
    module = load_module()
    dates = pd.date_range("2026-01-01", periods=6, freq="D")
    daily = pd.DataFrame(
        {
            "date": list(dates) + list(dates),
            "product_vt_symbol": ["a"] * 6 + ["b"] * 6,
            "net_pnl": range(12),
        }
    )

    result = module.add_future_path_metrics_and_label_end(daily, horizon=3)
    product_a = result[result.product_vt_symbol.eq("a")].sort_values("date")

    assert product_a[module.FUTURE_LABEL_END_COLUMN].iloc[0] == dates[3]
    assert product_a[module.FUTURE_LABEL_END_COLUMN].iloc[2] == dates[5]
    assert product_a[module.FUTURE_LABEL_END_COLUMN].iloc[3:].isna().all()


def test_pit_split_excludes_whole_month_when_one_product_label_ends_after_test() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(
                ["2024-05-31", "2024-05-31", "2024-06-30", "2024-06-30",
                 "2024-07-31", "2024-07-31", "2024-10-31", "2024-10-31"]
            ),
            "product_vt_symbol": ["a", "b"] * 4,
            module.FUTURE_LABEL_END_COLUMN: pd.to_datetime(
                ["2024-08-20", "2024-08-21", "2024-09-20", "2024-09-21",
                 "2024-10-30", "2024-11-01", "2025-01-30", "2025-01-31"]
            ),
        }
    )

    splits = module.build_pit_monthly_splits(frame, min_train_months=2)
    october = next(split for split in splits if split.test_date == pd.Timestamp("2024-10-31"))

    assert october.train_dates.tolist() == [
        pd.Timestamp("2024-05-31"),
        pd.Timestamp("2024-06-30"),
    ]
    assert october.train_label_end_max == pd.Timestamp("2024-09-21")
    assert october.purged_dates.tolist() == [pd.Timestamp("2024-07-31")]


def test_pit_split_accepts_label_ending_on_inference_date() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-07-31", "2024-08-31"]),
            "product_vt_symbol": ["a", "a"],
            module.FUTURE_LABEL_END_COLUMN: pd.to_datetime(["2024-08-31", "2024-09-30"]),
        }
    )

    splits = module.build_pit_monthly_splits(frame, min_train_months=1)

    assert len(splits) == 1
    assert splits[0].test_date == pd.Timestamp("2024-08-31")
    assert splits[0].train_dates.tolist() == [pd.Timestamp("2024-07-31")]


def test_pit_audit_detects_an_explicit_future_label_violation() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-07-31", "2024-10-31"]),
            "product_vt_symbol": ["a", "a"],
            module.FUTURE_LABEL_END_COLUMN: pd.to_datetime(["2024-11-01", "2025-01-31"]),
        }
    )
    invalid = module.PitMonthlySplit(
        train_dates=pd.DatetimeIndex([pd.Timestamp("2024-07-31")]),
        test_date=pd.Timestamp("2024-10-31"),
        train_label_end_max=pd.Timestamp("2024-11-01"),
        purged_dates=pd.DatetimeIndex([]),
    )

    audit = module.audit_pit_splits(frame, [invalid])

    assert audit["violation_rows"] == 1
    assert audit["violation_train_months"] == 1
    assert audit["violation_folds"] == 1
    assert audit["max_future_days"] == 1


def test_pit_audit_distinguishes_product_rows_from_one_leaking_train_month() -> None:
    module = load_module()
    products = [f"p{index:02d}" for index in range(18)]
    frame = pd.DataFrame(
        {
            "eval_date": [pd.Timestamp("2024-07-31")] * 18,
            "product_vt_symbol": products,
            module.FUTURE_LABEL_END_COLUMN: [pd.Timestamp("2024-11-01")] * 18,
        }
    )
    invalid = module.PitMonthlySplit(
        train_dates=pd.DatetimeIndex([pd.Timestamp("2024-07-31")]),
        test_date=pd.Timestamp("2024-10-31"),
        train_label_end_max=pd.Timestamp("2024-11-01"),
        purged_dates=pd.DatetimeIndex([]),
    )

    audit = module.audit_pit_splits(frame, [invalid])

    assert audit["violation_rows"] == 18
    assert audit["violation_train_months"] == 1
    assert audit["violation_folds"] == 1


def test_stage006_keeps_stage002_model_and_gate_contract_frozen() -> None:
    module = load_module()
    stage002 = module._load_stage002_module()

    assert module.XGBRANKER_PARAMS == stage002.XGBRANKER_PARAMS
    assert module.DUAL_PNL_WEIGHT == stage002.DUAL_PNL_WEIGHT == 0.5
    assert module.DUAL_DRAWDOWN_WEIGHT == stage002.DUAL_DRAWDOWN_WEIGHT == 0.5
    assert module.TOP_N == stage002.TOP_N == 10
    assert module.evaluate_candidate_gates is stage002.evaluate_candidate_gates


def test_stage006_decision_requires_zero_pit_violations_and_all_original_gates() -> None:
    module = load_module()
    qualification = {"passed": True, "gates": {"all_original_gates": True}}
    clean_audit = {
        "folds": 49,
        "violation_rows": 0,
        "violation_folds": 0,
        "max_future_days": 0,
    }

    assert module.stage006_decision(qualification, clean_audit) == (
        "stage006_pit_corrected_confirmed_pass_development_only"
    )
    assert module.stage006_decision(
        qualification,
        dict(clean_audit, violation_rows=1, violation_folds=1, max_future_days=1),
    ) == "stage006_pit_invalid_stop_no_backtest"
    assert module.stage006_decision(
        {"passed": False, "gates": {"all_original_gates": False}}, clean_audit
    ) == "stage006_pit_corrected_confirmed_fail_stop_no_backtest"
