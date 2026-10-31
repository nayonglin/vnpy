from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from build_qmt_roll_ai_position_training_samples import (
    FORWARD_WINDOWS,
    _clip,
    _extract_product_symbol,
    _locate_entry_index,
    _parse_vt_symbol,
    _safe_float,
    _safe_ratio,
    build_label_row,
    extract_market_features,
    load_contract_bars,
)
from run_qmt_alignment_backtest import (
    _build_trade_link_map,
    _match_entry_risk_to_trades,
    _normalize_trade_review_input,
)

PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

CANDIDATE_PATH: Path = OUTPUT_DIR / "qmt_roll_entry_candidate_snapshots_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / "qmt_roll_entry_risk_diagnostics_2020_2026_04.csv"
TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_trades_2020_2026_04.csv"

SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"
SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_schema.json"

CROSS_SECTIONAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "feature_ret_signed_5d",
    "feature_reversal_pressure_signed",
    "feature_mid_term_momentum_signed",
    "feature_trend_ma10_gap_pct",
    "feature_trend_ma20_gap_pct",
    "feature_ma5_ma10_gap_pct",
    "feature_ma10_ma20_gap_pct",
    "feature_ma20_ma40_gap_pct",
    "feature_close_vs_prev20_high_pct",
    "feature_close_vs_prev20_low_pct",
    "feature_atr14_pct",
    "feature_range_pct",
    "feature_atr14_pct_zscore_120",
    "feature_range_pct_zscore_120",
    "feature_ret_20d_zscore_120",
    "feature_upper_wick_pct",
    "feature_lower_wick_pct",
    "feature_vol20",
    "feature_vol60",
    "feature_volume_zscore_20",
    "feature_volume_ratio_1d_20d",
    "feature_volume_ratio_1d_20d_zscore_120",
    "feature_oi_delta_1d_pct",
    "feature_oi_delta_5d_pct",
    "feature_oi_delta_1d_pct_zscore_120",
    "feature_oi_ratio_2v2",
    "feature_volume_ratio_2v2",
    "feature_close_position_20d",
    "feature_close_position_60d",
    "feature_target_risk_to_equity",
    "feature_margin_per_contract_to_equity",
)


def _normalize_direction(value: object) -> str:
    direction = str(value).lower()
    if direction == "long":
        return "long"
    if direction == "short":
        return "short"
    return direction


def _selection_stage_from_reason(skip_reason: str) -> str:
    if not skip_reason:
        return "selected"
    if skip_reason in {"long_entry_disabled", "short_entry_disabled"}:
        return "entry_enable_gate"
    if skip_reason == "short_signal_rejected":
        return "direction_gate"
    if skip_reason == "concurrent_limit":
        return "position_limit_gate"
    if skip_reason == "sizing_zero_volume":
        return "sizing_gate"
    return "other_gate"


def _match_key(
    *,
    dt_value: object,
    product_vt_symbol: object,
    contract_vt_symbol: object,
    direction: object,
    signal: object,
    selected_volume: object,
) -> tuple[str, str, str, str, str, int]:
    dt_text = pd.Timestamp(dt_value).tz_localize(None).isoformat()
    return (
        dt_text,
        str(product_vt_symbol),
        str(contract_vt_symbol),
        _normalize_direction(direction),
        str(signal),
        int(_safe_float(selected_volume)),
    )


def build_opened_candidate_link_map(
    normalized_trades: pd.DataFrame,
    normalized_risks: pd.DataFrame,
) -> tuple[dict[tuple[str, str, str, str, str, int], deque[dict[str, Any]]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    risk_by_trade_id = _match_entry_risk_to_trades(normalized_trades, normalized_risks)
    trade_link_map = _build_trade_link_map(normalized_trades)
    trade_row_by_id = {str(row["trade_id"]): row for row in normalized_trades.to_dict("records")}

    opened_lookup: dict[tuple[str, str, str, str, str, int], deque[dict[str, Any]]] = defaultdict(deque)
    open_trades = normalized_trades[normalized_trades["offset"] == "Open"].copy()
    open_trades.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)

    for open_trade in open_trades.to_dict("records"):
        trade_id = str(open_trade["trade_id"])
        risk_row = risk_by_trade_id.get(trade_id)
        if risk_row is None:
            continue
        if str(risk_row.get("layer_kind", "")) != "base":
            continue

        linked_exit_ids = [str(item) for item in trade_link_map.get(trade_id, {}).get("exit_trade_ids", [])]
        linked_exit_rows = [trade_row_by_id[item] for item in linked_exit_ids if item in trade_row_by_id]
        key = _match_key(
            dt_value=risk_row["datetime"],
            product_vt_symbol=risk_row.get("product_vt_symbol", ""),
            contract_vt_symbol=risk_row.get("contract_vt_symbol", open_trade.get("vt_symbol", "")),
            direction=risk_row.get("direction", ""),
            signal=risk_row.get("signal", ""),
            selected_volume=risk_row.get("selected_volume", risk_row.get("volume", open_trade.get("volume", 0))),
        )
        opened_lookup[key].append(
            {
                "entry_trade_id": trade_id,
                "entry_trade_row": open_trade,
                "risk_row": risk_row,
                "linked_exit_rows": linked_exit_rows,
            }
        )

    return opened_lookup, risk_by_trade_id, trade_row_by_id


def build_candidate_market_label_row(candidate_row: dict[str, Any], bars_df: pd.DataFrame) -> dict[str, Any]:
    entry_date = pd.Timestamp(candidate_row["date"]).normalize()
    entry_index = _locate_entry_index(bars_df, entry_date)
    if entry_index is None:
        return {}

    entry_price = _safe_float(candidate_row.get("planned_entry_price"))
    stop_distance = _safe_float(candidate_row.get("stop_distance"))
    contract_size = max(_safe_float(candidate_row.get("size"), 1.0), 1.0)
    risk_per_contract = _safe_float(candidate_row.get("risk_per_contract"))
    effective_stop_distance = stop_distance
    if effective_stop_distance <= 0.0 and risk_per_contract > 0.0:
        effective_stop_distance = risk_per_contract / contract_size
    effective_stop_distance = max(effective_stop_distance, 1e-6)
    direction = _normalize_direction(candidate_row.get("direction", ""))
    direction_sign = 1.0 if direction == "long" else -1.0

    label_row: dict[str, Any] = {}
    label_row["label_candidate_effective_stop_distance"] = effective_stop_distance
    label_row["label_candidate_effective_stop_distance_pct"] = _safe_ratio(effective_stop_distance, entry_price)
    for forward_window in FORWARD_WINDOWS:
        forward_index = min(entry_index + forward_window, len(bars_df) - 1)
        forward_close = _safe_float(bars_df.iloc[forward_index]["close"], entry_price)
        signed_forward_return = direction_sign * _safe_ratio(forward_close - entry_price, entry_price)
        label_row[f"label_candidate_forward_{forward_window}d_return_pct"] = signed_forward_return
        label_row[f"label_candidate_forward_{forward_window}d_r_multiple"] = (
            _safe_ratio(forward_close - entry_price, effective_stop_distance) * direction_sign
        )

    lookahead_df = bars_df.iloc[entry_index : min(entry_index + 20, len(bars_df) - 1) + 1]
    lookahead_high = _safe_float(lookahead_df["high"].max(), entry_price)
    lookahead_low = _safe_float(lookahead_df["low"].min(), entry_price)
    if direction == "long":
        lookahead_mfe = lookahead_high - entry_price
        lookahead_mae = entry_price - lookahead_low
    else:
        lookahead_mfe = entry_price - lookahead_low
        lookahead_mae = lookahead_high - entry_price

    label_row["label_candidate_20d_mfe_r"] = _safe_ratio(lookahead_mfe, effective_stop_distance)
    label_row["label_candidate_20d_mae_r"] = _safe_ratio(lookahead_mae, effective_stop_distance)

    candidate_quality_score_v2 = (
        0.25 * _clip(label_row.get("label_candidate_forward_5d_r_multiple", 0.0), -3.0, 4.0)
        + 0.30 * _clip(label_row.get("label_candidate_forward_10d_r_multiple", 0.0), -3.0, 4.0)
        + 0.30 * _clip(label_row.get("label_candidate_forward_20d_r_multiple", 0.0), -3.0, 5.0)
        + 0.15
        * (
            _clip(label_row.get("label_candidate_20d_mfe_r", 0.0), 0.0, 6.0)
            - _clip(label_row.get("label_candidate_20d_mae_r", 0.0), 0.0, 4.0)
        )
    )
    label_row["label_candidate_quality_score_v2"] = candidate_quality_score_v2
    if candidate_quality_score_v2 >= 1.0:
        label_row["label_candidate_quality_bucket_v2"] = "large"
    elif candidate_quality_score_v2 >= 0.0:
        label_row["label_candidate_quality_bucket_v2"] = "normal"
    else:
        label_row["label_candidate_quality_bucket_v2"] = "small"
    return label_row


def add_candidate_cross_section_feature_columns(samples_df: pd.DataFrame) -> pd.DataFrame:
    if samples_df.empty:
        return samples_df

    enriched_df = samples_df.copy()
    group_size = enriched_df.groupby("candidate_date")["sample_id"].transform("count").astype("float64")
    enriched_df["feature_candidate_cross_section_count_1d"] = group_size

    for column in CROSS_SECTIONAL_FEATURE_COLUMNS:
        if column not in enriched_df.columns:
            continue

        rank_series = enriched_df.groupby("candidate_date")[column].rank(method="average").astype("float64")
        rank_pct = pd.Series(0.5, index=enriched_df.index, dtype="float64")
        mask = group_size > 1
        rank_pct.loc[mask] = (rank_series.loc[mask] - 1.0) / (group_size.loc[mask] - 1.0)
        rank_centered = (rank_pct - 0.5) * 2.0

        group_mean = enriched_df.groupby("candidate_date")[column].transform("mean").astype("float64")
        group_std = (
            enriched_df.groupby("candidate_date")[column].transform("std").astype("float64").replace(0.0, np.nan)
        )
        zscore = ((enriched_df[column].astype("float64") - group_mean) / group_std).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        enriched_df[f"{column}_cs_rank_pct_1d"] = rank_pct
        enriched_df[f"{column}_cs_rank_centered_1d"] = rank_centered
        enriched_df[f"{column}_cs_zscore_1d"] = zscore

    return enriched_df


def add_candidate_cross_section_labels(samples_df: pd.DataFrame) -> pd.DataFrame:
    if samples_df.empty:
        return samples_df

    enriched_df = samples_df.copy()
    group_size = enriched_df.groupby("candidate_date")["sample_id"].transform("count").astype("float64")
    enriched_df["label_candidate_cross_section_count_1d"] = group_size

    quality_rank = (
        enriched_df.groupby("candidate_date")["label_candidate_quality_score_v2"]
        .rank(method="average")
        .astype("float64")
    )
    quality_rank_pct = pd.Series(0.5, index=enriched_df.index, dtype="float64")
    mask = group_size > 1
    quality_rank_pct.loc[mask] = (quality_rank.loc[mask] - 1.0) / (group_size.loc[mask] - 1.0)
    enriched_df["label_candidate_quality_score_v2_rank_pct_1d"] = quality_rank_pct
    enriched_df["label_candidate_quality_score_v2_rank_centered_1d"] = (quality_rank_pct - 0.5) * 2.0

    selected_rank = (
        enriched_df.groupby("candidate_date")["label_is_selected"]
        .rank(method="average")
        .astype("float64")
    )
    selected_rank_pct = pd.Series(0.5, index=enriched_df.index, dtype="float64")
    selected_rank_pct.loc[mask] = (selected_rank.loc[mask] - 1.0) / (group_size.loc[mask] - 1.0)
    enriched_df["label_is_selected_rank_pct_1d"] = selected_rank_pct
    return enriched_df


def build_training_samples() -> tuple[pd.DataFrame, dict[str, int]]:
    candidate_df = pd.read_csv(CANDIDATE_PATH)
    entry_risk_df = pd.read_csv(ENTRY_RISK_PATH)
    trades_df = pd.read_csv(TRADES_PATH)

    normalized_trades = _normalize_trade_review_input(trades_df, "datetime")
    normalized_risks = _normalize_trade_review_input(entry_risk_df, "datetime")
    opened_lookup, _, _ = build_opened_candidate_link_map(normalized_trades, normalized_risks)

    candidate_df.sort_values(["datetime", "contract_vt_symbol", "candidate_index"], inplace=True)

    sample_rows: list[dict[str, Any]] = []
    matched_opened_count = 0
    unmatched_opened_count = 0
    skipped_count = 0
    missing_bar_count = 0
    feature_unavailable_count = 0
    market_label_unavailable_count = 0

    for candidate_row in candidate_df.to_dict("records"):
        vt_symbol = str(candidate_row["contract_vt_symbol"])
        bars_df = load_contract_bars(vt_symbol)
        if bars_df.empty:
            missing_bar_count += 1
            continue

        direction = _normalize_direction(candidate_row.get("direction", ""))
        signal = str(candidate_row.get("signal", ""))
        risk_mode = str(candidate_row.get("risk_mode", ""))
        candidate_date = pd.Timestamp(candidate_row["date"]).normalize()

        feature_row = extract_market_features(
            bars_df,
            entry_date=candidate_date,
            direction=direction,
            signal=signal,
            risk_mode=risk_mode,
        )
        if not feature_row:
            feature_unavailable_count += 1
            continue

        key = _match_key(
            dt_value=candidate_row["datetime"],
            product_vt_symbol=candidate_row.get("product_vt_symbol", ""),
            contract_vt_symbol=candidate_row.get("contract_vt_symbol", ""),
            direction=direction,
            signal=signal,
            selected_volume=candidate_row.get("selected_volume", 0),
        )
        linked_payload = opened_lookup[key].popleft() if opened_lookup.get(key) else None

        label_is_selected = int(str(candidate_row.get("candidate_status", "")) == "opened")
        if label_is_selected:
            if linked_payload is not None:
                matched_opened_count += 1
            else:
                unmatched_opened_count += 1
        else:
            skipped_count += 1

        selection_reason = "selected" if label_is_selected else str(candidate_row.get("skip_reason", "") or "unknown_skip_reason")
        market_label_row = build_candidate_market_label_row(candidate_row, bars_df)
        if not market_label_row:
            market_label_unavailable_count += 1
            continue

        actual_label_row: dict[str, Any] = {}
        entry_trade_id = ""
        if linked_payload is not None:
            entry_trade_id = str(linked_payload["entry_trade_id"])
            actual_label_row = build_label_row(
                entry_trade_id=entry_trade_id,
                entry_trade_row=linked_payload["entry_trade_row"],
                linked_exit_rows=linked_payload["linked_exit_rows"],
                risk_row=linked_payload["risk_row"],
                bars_df=bars_df,
            )

        sample_row: dict[str, Any] = {
            "sample_id": f"candidate_{int(_safe_float(candidate_row.get('candidate_index')))}",
            "candidate_index": int(_safe_float(candidate_row.get("candidate_index"))),
            "candidate_datetime": pd.Timestamp(candidate_row["datetime"]).isoformat(),
            "candidate_date": candidate_date.date().isoformat(),
            "product_vt_symbol": str(candidate_row.get("product_vt_symbol", "")),
            "contract_vt_symbol": vt_symbol,
            "exchange": _parse_vt_symbol(vt_symbol)[1],
            "contract_symbol": _parse_vt_symbol(vt_symbol)[0],
            "product_symbol": _extract_product_symbol(_parse_vt_symbol(vt_symbol)[0]),
            "entry_context": str(candidate_row.get("entry_context", "")),
            "direction": direction,
            "signal": signal,
            "risk_mode": risk_mode,
            "candidate_status": str(candidate_row.get("candidate_status", "")),
            "skip_reason": str(candidate_row.get("skip_reason", "")),
            "selection_stage": _selection_stage_from_reason(str(candidate_row.get("skip_reason", ""))),
            "entry_trade_id": entry_trade_id,
            "selected_contract_vt_symbol": str(linked_payload["risk_row"].get("contract_vt_symbol", vt_symbol)) if linked_payload else "",
            "entry_price": _safe_float(candidate_row.get("planned_entry_price")),
            "selected_entry_price": _safe_float(linked_payload["entry_trade_row"].get("price")) if linked_payload else 0.0,
            "entry_volume": _safe_float(candidate_row.get("selected_volume")),
            "selected_entry_volume": _safe_float(linked_payload["entry_trade_row"].get("volume")) if linked_payload else 0.0,
            "contract_size": _safe_float(candidate_row.get("size"), 1.0),
            "stop_price": _safe_float(candidate_row.get("stop_price")),
            "stop_distance": _safe_float(candidate_row.get("stop_distance")),
            "risk_ratio": _safe_float(candidate_row.get("risk_ratio")),
            "risk_multiplier": _safe_float(candidate_row.get("risk_multiplier")),
            "target_risk_amount": _safe_float(candidate_row.get("target_risk_amount")),
            "estimated_equity": _safe_float(candidate_row.get("estimated_equity")),
            "allowed_capital": _safe_float(candidate_row.get("allowed_capital")),
            "single_trade_capital_limit": _safe_float(candidate_row.get("single_trade_capital_limit")),
            "free_capital": _safe_float(candidate_row.get("free_capital")),
            "limited_balance": _safe_float(candidate_row.get("limited_balance")),
            "margin_ratio": _safe_float(candidate_row.get("margin_ratio")),
            "margin_per_contract": _safe_float(candidate_row.get("margin_per_contract")),
            "risk_per_contract": _safe_float(candidate_row.get("risk_per_contract")),
            "contracts_by_risk": _safe_float(candidate_row.get("contracts_by_risk")),
            "contracts_by_margin": _safe_float(candidate_row.get("contracts_by_margin")),
            "contracts_by_single_trade_cap": _safe_float(candidate_row.get("contracts_by_single_trade_cap")),
            "active_positions_before": int(_safe_float(candidate_row.get("active_positions_before"))),
            "max_concurrent_positions": int(_safe_float(candidate_row.get("max_concurrent_positions"))),
            "remaining_position_slots": int(_safe_float(candidate_row.get("remaining_position_slots"))),
            "loss_streak": int(_safe_float(candidate_row.get("loss_streak"))),
            "feature_source": "entry_candidate_snapshots + local_daily_csv + trades_for_selected",
            "feature_stop_distance_pct": _safe_ratio(_safe_float(candidate_row.get("stop_distance")), _safe_float(candidate_row.get("planned_entry_price"))),
            "feature_target_risk_to_equity": _safe_ratio(
                _safe_float(candidate_row.get("target_risk_amount")),
                _safe_float(candidate_row.get("estimated_equity")),
            ),
            "feature_margin_per_contract_to_equity": _safe_ratio(
                _safe_float(candidate_row.get("margin_per_contract")),
                _safe_float(candidate_row.get("estimated_equity")),
            ),
            "feature_allowed_capital_to_equity": _safe_ratio(
                _safe_float(candidate_row.get("allowed_capital")),
                _safe_float(candidate_row.get("estimated_equity")),
            ),
            "feature_single_trade_capital_limit_to_equity": _safe_ratio(
                _safe_float(candidate_row.get("single_trade_capital_limit")),
                _safe_float(candidate_row.get("estimated_equity")),
            ),
            "label_is_selected": label_is_selected,
            "label_selection_status": "selected" if label_is_selected else "skipped",
            "label_rejection_reason": selection_reason,
            "label_rejection_stage": _selection_stage_from_reason(str(candidate_row.get("skip_reason", ""))),
            "label_has_trade_link": int(linked_payload is not None),
        }
        sample_row.update(feature_row)
        sample_row.update(market_label_row)
        sample_row.update(actual_label_row)
        sample_rows.append(sample_row)

    samples_df = pd.DataFrame(sample_rows)
    samples_df.sort_values(["candidate_datetime", "candidate_index"], inplace=True)
    samples_df.reset_index(drop=True, inplace=True)
    samples_df = add_candidate_cross_section_feature_columns(samples_df)
    samples_df = add_candidate_cross_section_labels(samples_df)
    coverage = {
        "source_candidate_rows": int(len(candidate_df)),
        "source_selected_rows": int((candidate_df["candidate_status"] == "opened").sum()),
        "source_skipped_rows": int((candidate_df["candidate_status"] == "skipped").sum()),
        "candidate_rows": int(len(samples_df)),
        "selected_rows": int(samples_df["label_is_selected"].sum()) if not samples_df.empty else 0,
        "skipped_rows": int((samples_df["label_is_selected"] == 0).sum()) if not samples_df.empty else 0,
        "matched_opened_rows": int(matched_opened_count),
        "unmatched_opened_rows": int(unmatched_opened_count),
        "skipped_count_raw": int(skipped_count),
        "missing_bar_rows": int(missing_bar_count),
        "feature_unavailable_rows": int(feature_unavailable_count),
        "market_label_unavailable_rows": int(market_label_unavailable_count),
    }
    return samples_df, coverage


def build_schema(samples_df: pd.DataFrame, coverage: dict[str, int]) -> dict[str, Any]:
    categorical_columns = [
        column
        for column in samples_df.columns
        if column
        in {
            "product_vt_symbol",
            "contract_vt_symbol",
            "exchange",
            "contract_symbol",
            "product_symbol",
            "entry_context",
            "direction",
            "signal",
            "risk_mode",
            "candidate_status",
            "skip_reason",
            "selection_stage",
            "feature_signal",
            "feature_risk_mode",
            "feature_direction",
            "label_selection_status",
            "label_rejection_reason",
            "label_rejection_stage",
            "label_candidate_quality_bucket_v2",
            "label_size_bucket",
            "label_size_bucket_v2",
        }
    ]
    numeric_columns = [
        column
        for column in samples_df.columns
        if column
        not in categorical_columns
        and column not in {"sample_id", "candidate_datetime", "candidate_date", "entry_trade_id", "label_exit_date", "feature_source"}
    ]
    return {
        "dataset_name": "qmt_roll_ai_candidate_training_samples",
        "row_definition": "每一行对应一笔通过初筛的基础开仓候选，包含已被选中和未被选中的候选。",
        "target_recommendation": {
            "primary_classification_label": "label_is_selected",
            "secondary_classification_label": "label_rejection_reason",
            "primary_ranking_label": "label_candidate_quality_score_v2_rank_centered_1d",
            "alternative_regression_labels": [
                "label_candidate_quality_score_v2",
                "label_candidate_forward_10d_r_multiple",
                "label_candidate_forward_20d_r_multiple",
            ],
        },
        "coverage_summary": coverage,
        "categorical_columns": categorical_columns,
        "numeric_columns": numeric_columns,
        "feature_prefixes": ["feature_"],
        "label_prefixes": ["label_"],
        "notes": [
            "该数据集是第四版第二阶段产物，核心目标是把规则已选中样本扩展为完整候选池样本。",
            "label_is_selected/label_rejection_reason 用于模仿当前规则的选择与拦截逻辑。",
            "label_candidate_* 前缀标签基于候选当日价格构造统一前瞻结果，既适用于已选中候选，也适用于未选中候选。",
            "仅当候选实际被选中且成功对齐到 trade/risk 记录时，label_realized_* 等真实成交标签才会有值。",
            "当前候选集仅覆盖 flat_entry，不包含加仓和换月重开。",
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df, coverage = build_training_samples()
    samples_df.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(samples_df, coverage)
    SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-candidate-samples] rows: {len(samples_df)}")
    print(f"[ai-candidate-samples] samples csv: {SAMPLES_OUTPUT_PATH}")
    print(f"[ai-candidate-samples] schema json: {SCHEMA_OUTPUT_PATH}")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    if not samples_df.empty:
        preview_columns = [
            "candidate_date",
            "product_symbol",
            "direction",
            "signal",
            "candidate_status",
            "label_is_selected",
            "label_rejection_reason",
            "label_candidate_forward_10d_r_multiple",
            "label_candidate_quality_score_v2",
            "label_candidate_quality_score_v2_rank_centered_1d",
            "label_realized_r_multiple",
        ]
        preview_columns = [column for column in preview_columns if column in samples_df.columns]
        print(samples_df[preview_columns].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
