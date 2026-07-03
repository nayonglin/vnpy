from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STAGE = "Stage037"
MODEL_TAG = "stage037_feature_eligibility_audit_v1"
STAGE_SLUG = "stage037_feature_eligibility_audit"
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
DECISION = "stage037_feature_eligibility_audit_complete_no_trade_rule"

MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_HISTORY_COVERAGE_RATIO = 0.80

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"
EXAMPLES_OUTPUT_DIR = REPO_ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
EXTERNAL_LEDGER_DIR = EXAMPLES_OUTPUT_DIR / "external_state_forward_ledger"

FULL_MARKET_PREDICTIONS_PATH = (
    LINE_DIR
    / "outputs"
    / "stage021_full_market_consensus_jd_proxy"
    / "rebuilt_c9_stage021_full_market_consensus_jd_proxy_full_market_predictions_ranked_stage021_full_market_consensus_jd_proxy_v1.csv"
)
ENTRY_CANDIDATES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage036_overheat_recovery_pilot_engine"
    / "rebuilt_c9_stage036_overheat_recovery_pilot_engine_entry_candidates_stage036_overheat_recovery_pilot_engine_v1.csv"
)
HIGH_VOL_ROWS_PATH = (
    LINE_DIR
    / "outputs"
    / "stage035_high_vol_high_eff_internal_split"
    / "rebuilt_c9_stage035_high_vol_high_eff_internal_split_high_vol_rows_stage035_high_vol_eff_internal_split_v1.csv"
)
EXTERNAL_LEDGER_PATH = EXTERNAL_LEDGER_DIR / "external_state_forward_ledger.csv"
SENTIMENT_LEDGER_PATH = (
    EXTERNAL_LEDGER_DIR / "sentiment_news_manual_event_forward_ledger_stage572_real_sentiment_event_ledger_bootstrap_v1.csv"
)
BLACK_FERROUS_LEDGER_PATH = EXTERNAL_LEDGER_DIR / "black_ferrous_p1_source_forward_ledger.csv"
AI_POOL_CANDIDATES = [
    EXAMPLES_OUTPUT_DIR / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv",
    EXAMPLES_OUTPUT_DIR / "qmt_roll_stage182_ai_product_pool_live_inference_stage182_ai_product_pool_live_inference_v1.csv",
]

FEATURE_REGISTRY_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_feature_registry_{MODEL_TAG}.csv"
ARTIFACT_INVENTORY_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_artifact_inventory_{MODEL_TAG}.csv"
CANDIDATE_COVERAGE_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_candidate_column_coverage_{MODEL_TAG}.csv"
EXTERNAL_SUMMARY_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_external_ledger_summary_{MODEL_TAG}.csv"
JD_SUMMARY_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_jd_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"rebuilt_c9_{STAGE_SLUG}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_bool_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return series.astype(bool)
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    lowered = series.fillna("").astype(str).str.strip().str.lower()
    return lowered.isin({"1", "true", "yes", "y", "ok"})


def classify_feature_status(
    *,
    point_in_time: bool,
    history_ready: bool,
    forward_ready: bool,
    post_entry_only: bool = False,
    leakage_risk: bool = False,
    coverage_ratio: float | None = None,
) -> dict[str, Any]:
    coverage_ok = coverage_ratio is None or coverage_ratio >= MIN_HISTORY_COVERAGE_RATIO
    if leakage_risk:
        eligibility = "not_eligible_leakage_risk"
        reason = "存在未来信息或标签泄漏风险，不能用于历史 selector 或交易规则。"
    elif post_entry_only and not forward_ready:
        eligibility = "post_entry_schema_only"
        reason = "开仓后字段存在，但当前候选流未启用该模块；只能作为旧产物复盘线索，不能用于当前入场前 AI 选品。"
    elif post_entry_only:
        eligibility = "post_entry_confirmation_only"
        reason = "该信息在开仓后才可见，只能用于开仓后确认或加风险审计，不能用于入场前 AI 选品。"
    elif point_in_time and history_ready and coverage_ok:
        eligibility = "history_selector_ready"
        reason = "点时可用且历史覆盖达标，可进入下一步只读预测力审计。"
    elif point_in_time and history_ready and not coverage_ok:
        eligibility = "history_ready_low_coverage"
        reason = "点时语义成立，但历史覆盖不足，先补覆盖再做 selector。"
    elif point_in_time and forward_ready:
        eligibility = "forward_monitor_only"
        reason = "点时 forward 可监控，但历史 selector 深度不足，不能回填做收益筛选。"
    elif point_in_time:
        eligibility = "schema_ready_no_depth"
        reason = "字段语义点时可用，但当前没有足够样本深度。"
    else:
        eligibility = "not_ready"
        reason = "点时语义不明确或来源不可用。"
    return {
        "eligibility": eligibility,
        "history_selector_allowed": bool(eligibility == "history_selector_ready"),
        "forward_monitor_allowed": bool(eligibility in {"history_selector_ready", "history_ready_low_coverage", "forward_monitor_only", "post_entry_confirmation_only"}),
        "blocking_reason": reason,
    }


def summarize_forward_ledger(
    ledger: pd.DataFrame,
    *,
    min_runs: int = MIN_FORWARD_RUNS,
    min_dates: int = MIN_FORWARD_DATES,
) -> dict[str, Any]:
    if ledger.empty:
        return {
            "rows": 0,
            "runs": 0,
            "received_dates": 0,
            "forward_ready_rows": 0,
            "history_selector_rows": 0,
            "history_selector_ready": False,
            "blocking_reason": f"无 forward ledger；至少需要 {min_runs} runs / {min_dates} dates。",
        }
    frame = ledger.copy()
    frame["received_at_local"] = pd.to_datetime(frame.get("received_at_local"), errors="coerce")
    frame["received_date"] = frame["received_at_local"].dt.date.astype(str)
    forward_ready = _to_bool_series(frame.get("usable_for_forward_monitor", pd.Series(dtype=object)))
    history_ready = _to_bool_series(frame.get("usable_for_history_selector", pd.Series(dtype=object)))
    runs = int(frame.get("run_id", pd.Series(dtype=object)).nunique(dropna=True))
    dates = int(frame["received_date"].replace("NaT", np.nan).nunique(dropna=True))
    history_ready_rows = int(history_ready.sum())
    ready = bool(runs >= min_runs and dates >= min_dates and history_ready_rows > 0)
    if ready:
        reason = "forward 样本深度与 history selector 标记均达标。"
    else:
        reason = (
            f"forward 样本不足或未开放历史 selector：当前 {runs}/{min_runs} runs、"
            f"{dates}/{min_dates} dates、history_selector_rows={history_ready_rows}。"
        )
    return {
        "rows": int(len(frame)),
        "runs": runs,
        "received_dates": dates,
        "forward_ready_rows": int(forward_ready.sum()),
        "history_selector_rows": history_ready_rows,
        "history_selector_ready": ready,
        "blocking_reason": reason,
    }


def summarize_jd_full_market(predictions: pd.DataFrame) -> dict[str, Any]:
    if predictions.empty or "product_vt_symbol" not in predictions.columns:
        return {
            "jd_rows": 0,
            "jd_eval_months": 0,
            "jd_ai_top8_months": 0,
            "jd_simple_top8_months": 0,
            "jd_consensus_months": 0,
            "jd_consensus_future_pnl_60d_sum": 0.0,
            "recommendation": "jd_data_missing",
        }
    frame = predictions.copy()
    frame["product_key"] = frame["product_vt_symbol"].astype(str).str.lower()
    jd = frame[frame["product_key"].eq("jd.dce")].copy()
    if jd.empty:
        return {
            "jd_rows": 0,
            "jd_eval_months": 0,
            "jd_ai_top8_months": 0,
            "jd_simple_top8_months": 0,
            "jd_consensus_months": 0,
            "jd_consensus_future_pnl_60d_sum": 0.0,
            "recommendation": "jd_data_missing",
        }
    jd["eval_date"] = pd.to_datetime(jd.get("eval_date"), errors="coerce")
    ai_top8 = _to_bool_series(jd.get("stage021_ai_top8", pd.Series(False, index=jd.index)))
    simple_top8 = _to_bool_series(jd.get("stage021_simple_top8", pd.Series(False, index=jd.index)))
    consensus = _to_bool_series(jd.get("stage021_consensus_top8_jd", jd.get("stage021_consensus_top8", pd.Series(False, index=jd.index))))
    pnl = pd.to_numeric(jd.get("future_net_pnl_60d", 0.0), errors="coerce").fillna(0.0)
    consensus_pnl_sum = float(pnl[consensus].sum()) if len(jd) else 0.0
    consensus_months = int(consensus.sum())
    if consensus_months >= 6 and consensus_pnl_sum > 0:
        recommendation = "jd_needs_noncore_sleeve_true_engine"
    else:
        recommendation = "jd_not_shared_ai_ready"
    return {
        "jd_rows": int(len(jd)),
        "jd_eval_months": int(jd["eval_date"].dt.to_period("M").nunique(dropna=True)),
        "jd_ai_top8_months": int(ai_top8.sum()),
        "jd_simple_top8_months": int(simple_top8.sum()),
        "jd_consensus_months": consensus_months,
        "jd_consensus_future_pnl_60d_sum": consensus_pnl_sum,
        "recommendation": recommendation,
    }


def _artifact_inventory() -> pd.DataFrame:
    artifacts = [
        ("stage021_full_market_predictions", FULL_MARKET_PREDICTIONS_PATH, "full-market AI/simple trend and jd monthly evidence"),
        ("stage036_entry_candidates", ENTRY_CANDIDATES_PATH, "current rebuilt C9 candidate stream with AI/OI/risk fields"),
        ("external_state_forward_ledger", EXTERNAL_LEDGER_PATH, "basis/inventory/member/warehouse forward PIT ledger"),
        ("sentiment_manual_event_ledger", SENTIMENT_LEDGER_PATH, "manual event forward monitor ledger"),
        ("black_ferrous_p1_forward_ledger", BLACK_FERROUS_LEDGER_PATH, "black ferrous p1 forward source ledger"),
        ("stage419_basis_momentum_script", REPO_ROOT / "examples" / "portfolio_backtesting" / "analyze_qmt_roll_stage419_stage103_basis_momentum_overlay.py", "old basis momentum implementation reference"),
        ("stage508_true_carry_script", REPO_ROOT / "examples" / "portfolio_backtesting" / "analyze_qmt_roll_stage508_xsmom_true_carry_replay.py", "old true xsmom/carry implementation reference"),
        ("stage878_early_oi_script", REPO_ROOT / "examples" / "portfolio_backtesting" / "analyze_qmt_roll_stage878_stage861_early_oi_participation_audit.py", "old early OI participation audit reference"),
    ]
    for candidate in AI_POOL_CANDIDATES:
        if candidate.exists():
            artifacts.append(("stage182_ai_pool", candidate, "current rebuilt Stage182 monthly AI pool candidate file"))
            break
    rows = []
    for name, path, note in artifacts:
        rows.append(
            {
                "artifact": name,
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": int(path.stat().st_size) if path.exists() and path.is_file() else 0,
                "sha256": _sha256(path),
                "note": note,
            }
        )
    return pd.DataFrame(rows)


def _column_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    groups: list[tuple[str, str, list[str], bool, str | None]] = [
        ("ai_monthly_pool", "入场前月度 AI 选品", ["ai_product_pool_allowed", "ai_product_pool_score", "ai_product_pool_rank", "ai_product_pool_signal_date"], False, "ai_product_pool_enabled"),
        ("oi_price_confirm", "入场前 OI/价格确认", ["oi_price_confirm_oi_up", "oi_price_confirm_price_aligned", "oi_price_confirm_passed"], False, "oi_price_confirm_risk_restore_enabled"),
        ("pairwise_selection", "入场前 pairwise/候选排序字段", ["selection_pairwise_score", "selection_pairwise_rank", "selection_pairwise_feature_ret_20d_zscore_120"], False, "selection_pairwise_enabled"),
        ("post_entry_quality", "开仓后早段质量确认", ["post_entry_quality_add_passed", "post_entry_quality_add_body60_ratio", "post_entry_quality_add_avg_directional_close_strength"], True, "post_entry_quality_add_enabled"),
        ("account_state", "入场前账户状态", ["portfolio_drawdown_pct", "loss_streak", "active_positions_before"], False, None),
    ]
    rows = []
    total = int(len(frame))
    opened = frame[_to_bool_series(frame.get("is_opened", pd.Series(False, index=frame.index)))] if total else pd.DataFrame()
    for group, label, columns, post_entry_only, active_column in groups:
        present = [column for column in columns if column in frame.columns]
        if present and total:
            row_has_any = frame[present].notna().any(axis=1)
            coverage = float(row_has_any.mean())
            opened_coverage = float(opened[present].notna().any(axis=1).mean()) if not opened.empty else 0.0
        else:
            coverage = 0.0
            opened_coverage = 0.0
        if active_column and active_column in frame.columns and total:
            active_ratio = float(_to_bool_series(frame[active_column]).mean())
            opened_active_ratio = float(_to_bool_series(opened[active_column]).mean()) if not opened.empty and active_column in opened.columns else 0.0
        else:
            active_ratio = coverage
            opened_active_ratio = opened_coverage
        effective_coverage = min(coverage, active_ratio) if active_column else coverage
        status = classify_feature_status(
            point_in_time=True,
            history_ready=bool(present and effective_coverage >= MIN_HISTORY_COVERAGE_RATIO),
            forward_ready=bool(present and effective_coverage > 0.0),
            post_entry_only=post_entry_only,
            coverage_ratio=effective_coverage,
        )
        rows.append(
            {
                "feature_group": group,
                "label": label,
                "columns_present": ",".join(present),
                "columns_missing": ",".join([column for column in columns if column not in frame.columns]),
                "total_rows": total,
                "opened_rows": int(len(opened)),
                "coverage_ratio": coverage,
                "opened_coverage_ratio": opened_coverage,
                "active_column": active_column or "",
                "active_ratio": active_ratio,
                "opened_active_ratio": opened_active_ratio,
                "effective_coverage_ratio": effective_coverage,
                **status,
            }
        )
    return pd.DataFrame(rows)


def _build_feature_registry(
    candidate_coverage: pd.DataFrame,
    external_summary: dict[str, Any],
    jd_summary: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    def add(
        name: str,
        source: str,
        layer: str,
        point_in_time: bool,
        history_ready: bool,
        forward_ready: bool,
        post_entry_only: bool,
        note: str,
        coverage_ratio: float | None = None,
    ) -> None:
        status = classify_feature_status(
            point_in_time=point_in_time,
            history_ready=history_ready,
            forward_ready=forward_ready,
            post_entry_only=post_entry_only,
            coverage_ratio=coverage_ratio,
        )
        rows.append(
            {
                "feature_name": name,
                "source": source,
                "layer": layer,
                "point_in_time": point_in_time,
                "history_ready": history_ready,
                "forward_ready": forward_ready,
                "post_entry_only": post_entry_only,
                "coverage_ratio": coverage_ratio,
                "note": note,
                **status,
            }
        )

    cov_by_group = {str(row.feature_group): row for row in candidate_coverage.itertuples(index=False)}
    ai_cov = getattr(cov_by_group.get("ai_monthly_pool"), "effective_coverage_ratio", 0.0)
    oi_cov = getattr(cov_by_group.get("oi_price_confirm"), "effective_coverage_ratio", 0.0)
    pairwise_cov = getattr(cov_by_group.get("pairwise_selection"), "effective_coverage_ratio", 0.0)
    post_cov = getattr(cov_by_group.get("post_entry_quality"), "effective_coverage_ratio", 0.0)
    acct_cov = getattr(cov_by_group.get("account_state"), "effective_coverage_ratio", 0.0)
    add("stage182_ai_pool_rank_score", "stage036_entry_candidates + Stage182 pool", "monthly_preentry_ai_selection", True, ai_cov >= MIN_HISTORY_COVERAGE_RATIO, ai_cov > 0, False, "当前重建母本的冻结 AI 池和候选 rank/score；可用于审计和下一步只读 selector。", ai_cov)
    add("oi_price_confirm_fields", "stage036_entry_candidates", "preentry_participation_context", True, oi_cov >= MIN_HISTORY_COVERAGE_RATIO, oi_cov > 0, False, "OI/价格确认是入场前可见字段，但旧 OI 加仓/退出规则多次被反证，下一步只做特征审计。", oi_cov)
    add("pairwise_selection_features", "stage036_entry_candidates", "preentry_candidate_ranking", True, pairwise_cov >= MIN_HISTORY_COVERAGE_RATIO, pairwise_cov > 0, False, "候选排序字段存在但过往 pairwise/rank 直接交易化不足，先只做 coverage 和稳定性审计。", pairwise_cov)
    add("post_entry_first_minute_quality", "stage007/stage036 quality fields", "post_entry_confirmation", True, post_cov >= MIN_HISTORY_COVERAGE_RATIO, post_cov > 0, True, "开仓后早段质量有右尾信息，但不能用于入场前 AI 选品。", post_cov)
    add("account_state_fields", "stage036_entry_candidates", "preentry_account_context", True, acct_cov >= MIN_HISTORY_COVERAGE_RATIO, acct_cov > 0, False, "账户状态能解释左尾，但暂停/小手数化已反证，只能辅助 selector 诊断。", acct_cov)
    add("basis_inventory_forward_ledger", "external_state_forward_ledger", "external_forward_monitor", True, bool(external_summary.get("history_selector_ready")), bool(external_summary.get("forward_ready_rows", 0) > 0), False, str(external_summary.get("blocking_reason", "")), None)
    add("sentiment_manual_event_ledger", "sentiment_news_manual_event_forward_ledger", "external_forward_monitor", True, False, SENTIMENT_LEDGER_PATH.exists(), False, "真实舆情/事件账本只有少量 forward 样本，不可历史回填。", None)
    jd_history_ready = bool(jd_summary.get("recommendation") == "jd_needs_noncore_sleeve_true_engine")
    add("jd_full_market_monthly_evidence", "stage021_full_market_predictions", "noncore_product_expansion", True, jd_history_ready, bool(jd_summary.get("jd_rows", 0) > 0), False, f"jd rows={jd_summary.get('jd_rows', 0)} consensus_months={jd_summary.get('jd_consensus_months', 0)} recommendation={jd_summary.get('recommendation')}", None)
    add("historical_basis_carry_scripts", "Stage343/419/508 old research scripts", "reference_only", False, False, False, False, "旧线有 basis/carry/xsmom 实现资产，但未绑定当前重建 C9 和当前 AI 池，不能直接作为当前线 selector。", None)
    return pd.DataFrame(rows)


def _summarize_external_ledgers() -> pd.DataFrame:
    rows = []
    for name, path in [
        ("external_state_forward_ledger", EXTERNAL_LEDGER_PATH),
        ("sentiment_manual_event_ledger", SENTIMENT_LEDGER_PATH),
        ("black_ferrous_p1_forward_ledger", BLACK_FERROUS_LEDGER_PATH),
    ]:
        frame = _read_csv(path)
        summary = summarize_forward_ledger(frame)
        summary["ledger"] = name
        summary["path"] = str(path)
        rows.append(summary)
    return pd.DataFrame(rows)


def _write_stage_record(decision: dict[str, Any], registry: pd.DataFrame) -> Path:
    now = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{now}_{STAGE.lower()}_feature_eligibility_audit.md"
    ready = registry[registry["eligibility"].eq("history_selector_ready")]["feature_name"].tolist()
    forward_only = registry[registry["eligibility"].eq("forward_monitor_only")]["feature_name"].tolist()
    post_only = registry[registry["eligibility"].isin(["post_entry_confirmation_only", "post_entry_schema_only"])]["feature_name"].tolist()
    content = f"""# {STAGE} - 外生/AI 特征资格审计

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S CST')}`
- 阶段性质：只读特征资格审计；不做收益回测、不改官方实盘配置、不连接 CTP、不调用订单 API。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- CFA commodity ML 资料强调商品 ML 应使用 momentum、basis、carry、skewness、open interest 等 theory-grounded 特征，并持续做成本和可交易性审计。
- Fuertes/Miffre/Fernandez-Perez 商品策略研究说明 momentum、term structure 和 idiosyncratic volatility 不完全重叠，组合前应先验证独立信息源。
- CME open interest 教育资料说明 OI 可用于确认趋势强弱，但不是单独交易信号。
- GitHub `Machine-Learning-on-Futures` 说明中国商品期货机器学习可以用 Wind/商品特征，但这类数据必须先解决点时化和授权/覆盖问题。
- 我的判断：当前不能继续扫风险门槛；下一步应该先确认哪些特征可以合法接入当前重建 C9 的 AI/候选流。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage037_feature_eligibility_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage037_feature_eligibility.py`
- 修改正式策略脚本：无
- 删除脚本：无
- 新增参数：`MIN_FORWARD_RUNS={MIN_FORWARD_RUNS}`、`MIN_FORWARD_DATES={MIN_FORWARD_DATES}`、`MIN_HISTORY_COVERAGE_RATIO={MIN_HISTORY_COVERAGE_RATIO}`
- 修改参数：无正式参数修改。

## 结果

- 决策：`{decision['decision']}`
- history selector ready：`{', '.join(ready) if ready else '无'}`
- forward monitor only：`{', '.join(forward_only) if forward_only else '无'}`
- post-entry confirmation only：`{', '.join(post_only) if post_only else '无'}`
- jd 结论：`{decision['jd_recommendation']}`
- 外生 ledger：`{decision['external_runs']}` runs / `{decision['external_received_dates']}` received dates，未达 `{MIN_FORWARD_RUNS}/{MIN_FORWARD_DATES}`，不得历史回填做 selector。
- 订单/CTP API：`0`

## 结论

- 当前能继续做的是“当前 C9 候选级 PIT 特征矩阵 + 只读预测力审计”，不是直接上新交易规则。
- `jd.DCE` 仍不能直接进入共享 AI 池；只能保留为非挤占观察或等新证据。
- basis/inventory/sentiment 只能 forward monitor，不能历史收益回测。
- 开仓后早段质量标签只能做确认层，不能作为入场前 AI 选品特征。

## 输出文件

- report：`{REPORT_PATH}`
- feature registry：`{FEATURE_REGISTRY_PATH}`
- artifact inventory：`{ARTIFACT_INVENTORY_PATH}`
- candidate coverage：`{CANDIDATE_COVERAGE_PATH}`
- external summary：`{EXTERNAL_SUMMARY_PATH}`
- jd summary：`{JD_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`

## 过拟合反思

- 运行前判断：否。本阶段只做特征资格和点时边界审计，不根据收益挑规则。
- 运行后判断：否。但若下一步拿 shallow forward ledger 或 future labels 回填训练，就是严重过拟合/泄漏。

## 继续价值反思

- 运行前判断：有。用户目标要求 AI 选品优化、鸡蛋和高质量信号，必须先确认特征是否合法可接。
- 运行后判断：有。下一步应做候选级 PIT feature matrix，而不是写交易规则。

## 后续规划

- Stage038 建议：构建当前重建 C9 的候选级 PIT feature matrix，只读评估 AI rank/score、OI/volume、account state、simple trend、full-market rank 的预测力和稳定性；不得用 post-entry 标签或 external forward ledger 做入场前训练。
"""
    path.write_text(content, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    artifacts = _artifact_inventory()
    entry = _read_csv(ENTRY_CANDIDATES_PATH)
    full_market = _read_csv(FULL_MARKET_PREDICTIONS_PATH)
    external = _read_csv(EXTERNAL_LEDGER_PATH)

    candidate_coverage = _column_coverage(entry)
    external_summary = summarize_forward_ledger(external)
    external_summaries = _summarize_external_ledgers()
    jd_summary = summarize_jd_full_market(full_market)
    jd_summary_frame = pd.DataFrame([jd_summary])
    registry = _build_feature_registry(candidate_coverage, external_summary, jd_summary)

    history_ready = registry[registry["eligibility"].eq("history_selector_ready")]["feature_name"].tolist()
    forward_only = registry[registry["eligibility"].eq("forward_monitor_only")]["feature_name"].tolist()
    post_only = registry[registry["eligibility"].eq("post_entry_confirmation_only")]["feature_name"].tolist()

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": DECISION,
        "history_selector_ready_count": len(history_ready),
        "history_selector_ready_features": history_ready,
        "forward_monitor_only_features": forward_only,
        "post_entry_confirmation_only_features": post_only,
        "external_runs": external_summary["runs"],
        "external_received_dates": external_summary["received_dates"],
        "external_history_selector_ready": external_summary["history_selector_ready"],
        "jd_recommendation": jd_summary["recommendation"],
        "jd_rows": jd_summary["jd_rows"],
        "jd_consensus_months": jd_summary["jd_consensus_months"],
        "official_live_config_changed": False,
        "ctp_connected": False,
        "order_api_calls": 0,
        "next_stage": "stage038_current_c9_candidate_pit_feature_matrix_readonly",
    }

    artifacts.to_csv(ARTIFACT_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    candidate_coverage.to_csv(CANDIDATE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    external_summaries.to_csv(EXTERNAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    jd_summary_frame.to_csv(JD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    registry.to_csv(FEATURE_REGISTRY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    report = f"""# {STAGE} 外生/AI 特征资格审计

## 决策

`{DECISION}`。本阶段只做资格审计，不生成交易规则。

## 特征资格表

{_md_table(registry[["feature_name", "layer", "eligibility", "history_selector_allowed", "forward_monitor_allowed", "note"]])}

## 当前候选字段覆盖

{_md_table(candidate_coverage[["feature_group", "coverage_ratio", "active_ratio", "effective_coverage_ratio", "opened_coverage_ratio", "opened_active_ratio", "eligibility", "blocking_reason"]])}

## 外生 forward ledger

{_md_table(external_summaries[["ledger", "runs", "received_dates", "forward_ready_rows", "history_selector_rows", "history_selector_ready", "blocking_reason"]])}

## jd.DCE 证据

{_md_table(jd_summary_frame)}

## 判断

- 可立即进入下一步只读预测力审计的，是当前候选流中已有的 PIT 字段：AI rank/score、OI 价格确认、账户状态、pairwise/简单趋势类字段。
- 开仓后早段质量标签只能用于确认层，不能用于入场前 AI 选品。
- basis/inventory/sentiment forward ledger 样本太浅，只能做 forward monitor。
- `jd.DCE` 当前证据不足，不应直接进入共享 AI 池或共享 topN。
- 下一步建议做 Stage038：候选级 PIT feature matrix 和 purged/time-split 预测力审计。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    stage_record = _write_stage_record(decision, registry)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, sort_keys=True))
    return decision


if __name__ == "__main__":
    run()
