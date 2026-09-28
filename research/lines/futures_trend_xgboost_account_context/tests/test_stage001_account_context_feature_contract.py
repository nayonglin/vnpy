from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage001_account_context_feature_contract.py"
)


def load_module():
    assert MODULE_PATH.exists(), (
        "Stage001 account-context feature contract is not implemented"
    )
    spec = importlib.util.spec_from_file_location(
        "stage001_account_context_feature_contract", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deterministic_vectors() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    top9 = np.tile(np.array([2.0, -2.0, 1.0, -1.0]), 30)
    rank10 = 0.5 * top9
    challenger = -0.5 * top9
    return top9, rank10, challenger


def test_context_feature_names_are_exactly_frozen() -> None:
    module = load_module()

    assert module.CONTEXT_FEATURE_COLUMNS == [
        "candidate_top9_aggregate_corr_120d_delta_vs_rank10",
        "candidate_top9_downside_corr_120d_delta_vs_rank10",
        "candidate_top9_active_overlap_rate_120d_delta_vs_rank10",
        "candidate_top9_joint_loss_rate_120d_delta_vs_rank10",
        "top9_plus_candidate_drawdown_improvement_ratio_120d_vs_rank10",
        "top9_plus_candidate_sharpe_improvement_120d_vs_rank10",
    ]
    assert module.WINDOW_DAYS == 120
    assert module.MIN_DOWNSIDE_DAYS == 20


def test_context_deltas_match_hand_calculation() -> None:
    module = load_module()
    top9, rank10, challenger = deterministic_vectors()

    result = module.compute_context_feature_deltas(top9, rank10, challenger)

    assert list(result) == module.CONTEXT_FEATURE_COLUMNS
    assert result[module.CONTEXT_FEATURE_COLUMNS[0]] == pytest.approx(-2.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[1]] == pytest.approx(-2.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[2]] == pytest.approx(0.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[3]] == pytest.approx(-0.5)
    assert result[module.CONTEXT_FEATURE_COLUMNS[4]] == pytest.approx(2.0 / 3.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[5]] == pytest.approx(
        0.0, abs=1e-15
    )


def test_rank10_self_comparison_is_exact_zero() -> None:
    module = load_module()
    top9, rank10, _ = deterministic_vectors()

    result = module.compute_context_feature_deltas(
        top9, rank10, rank10.copy()
    )

    assert result == {
        name: 0.0 for name in module.CONTEXT_FEATURE_COLUMNS
    }


@pytest.mark.parametrize(
    ("top9", "rank10", "candidate", "code"),
    [
        (
            np.ones(119),
            np.ones(119),
            np.ones(119),
            "context_window_length_not_120",
        ),
        (
            np.r_[np.array([-2.0, -1.0] * 9), -1.0, np.ones(101)],
            np.tile(np.array([1.0, 2.0]), 60),
            np.tile(np.array([2.0, 1.0]), 60),
            "top9_downside_days_below_20",
        ),
        (
            np.tile(np.array([1.0, -1.0]), 60),
            np.zeros(120),
            np.tile(np.array([1.0, -1.0]), 60),
            "rank10_activity_days_zero",
        ),
        (
            np.tile(np.array([1.0, -1.0]), 60),
            np.tile(np.array([1.0, -1.0]), 60),
            np.full(120, np.nan),
            "context_vector_nonfinite",
        ),
    ],
)
def test_context_contract_rejects_invalid_vectors(
    top9: np.ndarray,
    rank10: np.ndarray,
    candidate: np.ndarray,
    code: str,
) -> None:
    module = load_module()

    with pytest.raises(module.Stage001ContractError, match=f"^{code}$"):
        module.compute_context_feature_deltas(top9, rank10, candidate)


BASE_FEATURE_COLUMNS = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    "pnl120_z_delta_vs_rank10",
    "pnl60_z_delta_vs_rank10",
    "sharpe60_z_delta_vs_rank10",
    "positive_day60_z_delta_vs_rank10",
    "opened60_z_delta_vs_rank10",
    "slippage60_z_delta_vs_rank10",
    "drawdown60_z_delta_vs_rank10",
]


def one_month_pit_fixture() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.Timestamp,
]:
    dates = pd.bdate_range(end="2022-06-30", periods=121)
    eval_date = dates[-2]
    products = [f"p{rank}.TEST" for rank in range(1, 19)]
    top9 = np.tile(np.array([2.0, -2.0, 1.0, -1.0]), 30)
    values: dict[str, np.ndarray] = {}
    for rank, product in enumerate(products, start=1):
        if rank == 1:
            series = np.r_[top9, 0.0]
        elif rank <= 9:
            series = np.zeros(121)
        elif rank == 10:
            series = np.r_[0.5 * top9, 0.0]
        elif rank == 11:
            series = np.r_[-0.5 * top9, 1_000_000.0]
        else:
            series = np.r_[0.25 * top9, 0.0]
        values[product] = series

    daily_rows = [
        {
            "date": date,
            "product_vt_symbol": product,
            "net_pnl": float(values[product][index]),
        }
        for index, date in enumerate(dates)
        for product in products
    ]
    ranking = pd.DataFrame(
        {
            "eval_date": [eval_date] * 18,
            "product_vt_symbol": products,
            "score_rank": list(range(1, 19)),
        }
    )
    base_rows = []
    for rank in range(10, 19):
        row: dict[str, object] = {
            "eval_date": eval_date,
            "next_eval_date": pd.Timestamp("2022-07-29"),
            "product_vt_symbol": f"p{rank}.TEST",
            "score_rank": rank,
            "score_type": "ai_probability_top19_plus_fixed_fu",
            "split": "development",
            "label_values_read_allowed": True,
        }
        row.update({name: 0.0 for name in BASE_FEATURE_COLUMNS})
        base_rows.append(row)
    return (
        pd.DataFrame(base_rows),
        ranking,
        pd.DataFrame(daily_rows),
        eval_date,
    )


def test_product_daily_matches_formal_contract_mapping_and_zero_grid() -> None:
    module = load_module()
    raw = pd.DataFrame(
        {
            "date": ["2022-01-03", "2022-01-03", "2022-01-04"],
            "vt_symbol": ["AP205.CZCE", "AP209.CZCE", "rb2205.SHFE"],
            "net_pnl": [10.0, -3.0, 5.0],
        }
    )

    result = module.build_product_daily(
        raw, ["AP.CZCE", "rb.SHFE"]
    )
    pivot = result.pivot(
        index="date", columns="product_vt_symbol", values="net_pnl"
    )

    assert pivot.loc[pd.Timestamp("2022-01-03"), "AP.CZCE"] == 7.0
    assert pivot.loc[pd.Timestamp("2022-01-03"), "rb.SHFE"] == 0.0
    assert pivot.loc[pd.Timestamp("2022-01-04"), "AP.CZCE"] == 0.0
    assert pivot.loc[pd.Timestamp("2022-01-04"), "rb.SHFE"] == 5.0


def test_monthly_context_panel_uses_only_dates_through_eval_date() -> None:
    module = load_module()
    base, ranking, daily, eval_date = one_month_pit_fixture()

    panel, audit = module.build_context_feature_panel(
        base, ranking, daily
    )

    rank10 = panel.loc[
        panel["score_rank"].eq(10), module.CONTEXT_FEATURE_COLUMNS
    ]
    rank11 = panel.loc[panel["score_rank"].eq(11)].iloc[0]
    expected_start = (
        daily.loc[daily["date"].le(eval_date), "date"]
        .drop_duplicates()
        .sort_values()
        .iloc[-120]
    )
    assert len(panel) == 9
    assert panel["score_rank"].tolist() == list(range(10, 19))
    assert (rank10.to_numpy(float) == 0.0).all()
    assert rank11[module.CONTEXT_FEATURE_COLUMNS[0]] == pytest.approx(-2.0)
    assert rank11[module.CONTEXT_FEATURE_COLUMNS[3]] == pytest.approx(-0.5)
    assert audit.to_dict("records") == [
        {
            "eval_date": eval_date.normalize(),
            "window_start": expected_start,
            "window_end": eval_date.normalize(),
            "window_days": 120,
            "top9_downside_days": 60,
            "rank_count": 18,
            "candidate_count": 9,
            "max_source_date_used": eval_date.normalize(),
        }
    ]


def test_future_position_change_cannot_change_any_feature() -> None:
    module = load_module()
    base, ranking, daily, eval_date = one_month_pit_fixture()
    first, _ = module.build_context_feature_panel(base, ranking, daily)
    future = daily["date"].gt(eval_date) & daily[
        "product_vt_symbol"
    ].eq("p11.TEST")
    daily.loc[future, "net_pnl"] = -9_000_000_000.0

    second, _ = module.build_context_feature_panel(base, ranking, daily)

    pd.testing.assert_frame_equal(first, second, check_exact=True)


def test_missing_rank_or_short_window_is_a_hard_failure() -> None:
    module = load_module()
    base, ranking, daily, _ = one_month_pit_fixture()
    with pytest.raises(
        module.Stage001ContractError,
        match="^formal_ranking_month_ranks_not_1_to_18$",
    ):
        module.build_context_feature_panel(
            base, ranking[ranking["score_rank"].ne(7)], daily
        )
    short = daily[
        daily["date"].isin(sorted(daily["date"].unique())[-119:])
    ]
    with pytest.raises(
        module.Stage001ContractError,
        match="^context_window_dates_below_120$",
    ):
        module.build_context_feature_panel(base, ranking, short)


def test_frozen_input_identities_and_stage_scope_are_exact() -> None:
    module = load_module()

    assert module.EXPECTED_SHA256 == {
        "formal_full_ranking": (
            "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0"
        ),
        "base_feature_panel": (
            "e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd"
        ),
        "position_changes": (
            "17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa"
        ),
        "spec": (
            "1591494f782fd12c6d5fd4bb2da48d9d0b7c1d54b0bfedb7616d9cb61f565d34"
        ),
    }
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "development_labels.csv" not in source
    assert "sealed_holdout_labels" not in source
    assert "import xgboost" not in source
    assert "from xgboost" not in source


def test_identity_drift_stops_before_any_csv_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    tampered = tmp_path / "ranking.csv"
    tampered.write_text("tampered\n", encoding="utf-8")
    paths = dict(module.INPUT_PATHS)
    paths["formal_full_ranking"] = tampered
    calls: list[object] = []
    monkeypatch.setattr(
        module.pd,
        "read_csv",
        lambda *args, **kwargs: calls.append(args[0]),
    )

    with pytest.raises(
        module.Stage001ContractError,
        match="^input_sha256_drift:formal_full_ranking$",
    ):
        module.run_stage001(tmp_path / "out", input_paths=paths)

    assert calls == []


def test_real_frozen_inputs_fail_deterministically_without_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    original_read_csv = module.pd.read_csv
    calls: list[str] = []

    def recording_read_csv(path, *args, **kwargs):
        calls.append(str(path))
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(module.pd, "read_csv", recording_read_csv)
    for output_dir in (first_dir, second_dir):
        with pytest.raises(
            module.Stage001ContractError,
            match="^candidate_activity_days_zero$",
        ):
            module.run_stage001(output_dir)
        assert not output_dir.exists()
        assert not output_dir.with_name(f"{output_dir.name}.tmp").exists()

    allowed_reads = {
        str(module.INPUT_PATHS["formal_full_ranking"]),
        str(module.INPUT_PATHS["base_feature_panel"]),
        str(module.INPUT_PATHS["position_changes"]),
    }
    assert calls == sorted(allowed_reads) * 2
