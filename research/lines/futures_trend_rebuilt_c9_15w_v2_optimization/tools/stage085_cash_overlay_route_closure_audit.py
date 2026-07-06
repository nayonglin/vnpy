from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage085"
MODEL_TAG = "stage085_cash_overlay_route_closure_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage085_cash_overlay_route_closure_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage085_cash_overlay_route_closure_audit"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_inventory_{MODEL_TAG}.csv"
PASSING_PATH = OUT / f"{OUTPUT_PREFIX}_passing_but_not_promoted_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


SOURCES = [
    {
        "stage": "Stage073",
        "path": LINE_DIR
        / "outputs/stage073_official_c9_path_governance_proxy/rebuilt_c9_v2_stage073_official_c9_path_governance_proxy_variant_summary_stage073_official_c9_path_governance_proxy_v1.csv",
        "source_type": "path_governance_proxy",
        "engine_level": "curve_proxy",
        "route_bucket": "drawdown_brake",
    },
    {
        "stage": "Stage074",
        "path": LINE_DIR
        / "outputs/stage074_official_c9_30w_buffer_topup_proxy/rebuilt_c9_v2_stage074_official_c9_30w_buffer_topup_proxy_variant_summary_stage074_official_c9_30w_buffer_topup_proxy_v1.csv",
        "source_type": "buffer_topup_proxy",
        "engine_level": "curve_proxy",
        "route_bucket": "reserve_internal_transfer",
    },
    {
        "stage": "Stage075",
        "path": LINE_DIR
        / "outputs/stage075_official_c9_monthend_buffer_topup_true_engine/rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine_variant_summary_stage075_official_c9_monthend_buffer_topup_true_engine_v1.csv",
        "source_type": "buffer_topup_true_engine",
        "engine_level": "true_engine",
        "route_bucket": "reserve_internal_transfer",
    },
    {
        "stage": "Stage076",
        "path": LINE_DIR
        / "outputs/stage076_c9_plus_stage372_reserve_sleeve_proxy/rebuilt_c9_v2_stage076_c9_plus_stage372_reserve_sleeve_proxy_variant_summary_stage076_c9_plus_stage372_reserve_sleeve_proxy_v1.csv",
        "source_type": "legacy_sleeve_proxy",
        "engine_level": "curve_proxy",
        "route_bucket": "separate_sleeve_proxy",
    },
    {
        "stage": "Stage077",
        "path": LINE_DIR
        / "outputs/stage077_c9_idle_reserve_cash_yield_proxy/rebuilt_c9_v2_stage077_c9_idle_reserve_cash_yield_proxy_variant_summary_stage077_c9_idle_reserve_cash_yield_proxy_v2.csv",
        "source_type": "constant_cash_yield_proxy",
        "engine_level": "cash_yield_proxy",
        "route_bucket": "idle_reserve_yield",
    },
    {
        "stage": "Stage078",
        "path": LINE_DIR
        / "outputs/stage078_real_cash_yield_source_audit/rebuilt_c9_v2_stage078_real_cash_yield_source_audit_variant_summary_stage078_real_cash_yield_source_audit_v1.csv",
        "source_type": "real_cash_yield_source_audit",
        "engine_level": "source_audit",
        "route_bucket": "idle_reserve_yield",
    },
    {
        "stage": "Stage081",
        "path": LINE_DIR
        / "outputs/stage081_fixed_money_fund_basket_replay/rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_variant_summary_stage081_fixed_money_fund_basket_replay_v1.csv",
        "source_type": "fixed_money_fund_basket",
        "engine_level": "cash_yield_proxy",
        "route_bucket": "idle_reserve_yield",
    },
    {
        "stage": "Stage082",
        "path": LINE_DIR
        / "outputs/stage082_conservative_money_fund_basket_replay/rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay_variant_summary_stage082_conservative_money_fund_basket_replay_v1.csv",
        "source_type": "conservative_money_fund_basket",
        "engine_level": "cash_yield_proxy",
        "route_bucket": "idle_reserve_yield",
    },
    {
        "stage": "Stage083",
        "path": LINE_DIR
        / "outputs/stage083_money_fund_friction_sensitivity/rebuilt_c9_v2_stage083_money_fund_friction_sensitivity_variant_summary_stage083_money_fund_friction_sensitivity_v1.csv",
        "source_type": "money_fund_friction_sensitivity",
        "engine_level": "cash_yield_proxy",
        "route_bucket": "idle_reserve_yield",
    },
    {
        "stage": "Stage084",
        "path": LINE_DIR
        / "outputs/stage084_businessday_nonnegative_haircut_replay/rebuilt_c9_v2_stage084_businessday_nonnegative_haircut_replay_variant_summary_stage084_businessday_nonnegative_haircut_replay_v1.csv",
        "source_type": "businessday_nonnegative_haircut",
        "engine_level": "cash_yield_proxy",
        "route_bucket": "idle_reserve_yield",
    },
]


MANUAL_VERDICTS = {
    "Stage073": "not_promoted: drawdown brake worsens right tail/water",
    "Stage074": "not_promoted_after_true_engine: proxy passed but Stage075 failed",
    "Stage075": "not_promoted: true engine retention/water target failed",
    "Stage076": "not_promoted: legacy reserve sleeve did not shorten water robustly",
    "Stage077": "not_promoted: constant yield proxy lacks accepted real source",
    "Stage078": "not_promoted: no accepted real cash source",
    "Stage081": "not_promoted: weak account-level cash basket proxy",
    "Stage082": "not_promoted: conservative basket still aggregate/weak",
    "Stage083": "not_promoted: friction pass only under light cost and edge thin",
    "Stage084": "not_promoted: business-day/floor0 confirms weak account layer",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if not np.isfinite(result) else result
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, Path):
        return str(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _as_float(row: pd.Series, *columns: str) -> float:
    for column in columns:
        if column in row.index:
            value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
            if pd.notna(value):
                return float(value)
    return np.nan


def _as_int(row: pd.Series, *columns: str) -> int | None:
    value = _as_float(row, *columns)
    if not np.isfinite(value):
        return None
    return int(value)


def _as_bool(row: pd.Series, *columns: str) -> bool | None:
    for column in columns:
        if column not in row.index:
            continue
        value = row[column]
        if isinstance(value, bool):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return None


def _bool_series(series: pd.Series) -> pd.Series:
    def convert(value: Any) -> bool:
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if value is None:
            return False
        try:
            if pd.isna(value):
                return False
        except (TypeError, ValueError):
            pass
        text = str(value).strip().lower()
        return text in {"true", "1", "yes"}

    return series.map(convert).astype(bool)


def _is_official(version: str, label: str) -> bool:
    text = f"{version} {label}".lower()
    return "official" in text and ("reference" in text or "c9/15w" in text or "c9 15w" in text)


def _canonicalize(source: dict[str, Any]) -> pd.DataFrame:
    raw = _read_csv(source["path"])
    if raw.empty:
        return pd.DataFrame(
            [
                {
                    "stage": source["stage"],
                    "source_path": str(source["path"]),
                    "source_status": "missing_or_empty",
                    "source_type": source["source_type"],
                    "engine_level": source["engine_level"],
                    "route_bucket": source["route_bucket"],
                }
            ]
        )
    rows: list[dict[str, Any]] = []
    official = raw[
        raw.apply(lambda row: _is_official(str(row.get("version", "")), str(row.get("variant_label", ""))), axis=1)
    ].copy()
    official_row = official.iloc[0] if not official.empty else None
    official_dd = _as_float(official_row, "worst_drawdown_pct") if official_row is not None else np.nan
    official_days = _as_int(official_row, "max_days_below_initial") if official_row is not None else None
    official_consec = _as_int(official_row, "max_consecutive_below_initial_days") if official_row is not None else None
    for _, row in raw.iterrows():
        version = str(row.get("version", ""))
        label = str(row.get("variant_label", version))
        is_official = _is_official(version, label)
        min_retention = _as_float(row, "min_return_retention_ratio")
        median_retention = _as_float(row, "median_return_retention_ratio")
        worst_dd = _as_float(row, "worst_drawdown_pct")
        max_days = _as_int(row, "max_days_below_initial")
        max_consecutive = _as_int(row, "max_consecutive_below_initial_days")
        published_pass = _as_bool(
            row,
            "passes_new_goal_vs_official",
            "passes_account_level_stage077_proxy_goal",
            "passes_goal_vs_official",
            "passes_new_goal",
        )
        computed_pass = False
        if (
            not is_official
            and np.isfinite(min_retention)
            and np.isfinite(worst_dd)
            and official_days is not None
            and official_consec is not None
            and max_days is not None
            and max_consecutive is not None
        ):
            computed_pass = (
                min_retention >= 0.5
                and worst_dd > official_dd
                and max_days < official_days
                and max_consecutive < official_consec
            )
        rows.append(
            {
                "stage": source["stage"],
                "source_path": str(source["path"]),
                "source_status": "loaded",
                "source_type": source["source_type"],
                "engine_level": source["engine_level"],
                "route_bucket": source["route_bucket"],
                "version": version,
                "variant_label": label,
                "is_official_reference": is_official,
                "start_count": _as_int(row, "start_count"),
                "positive_count": _as_int(row, "positive_count"),
                "min_return_pct": _as_float(row, "min_return_pct"),
                "median_return_pct": _as_float(row, "median_return_pct"),
                "max_return_pct": _as_float(row, "max_return_pct"),
                "min_return_retention_ratio": min_retention,
                "median_return_retention_ratio": median_retention,
                "worst_drawdown_pct": worst_dd,
                "median_drawdown_pct": _as_float(row, "median_drawdown_pct"),
                "max_days_below_initial": max_days,
                "median_days_below_initial": _as_float(row, "median_days_below_initial"),
                "max_consecutive_below_initial_days": max_consecutive,
                "median_consecutive_below_initial_days": _as_float(
                    row, "median_consecutive_below_initial_days"
                ),
                "published_pass": published_pass,
                "computed_account_level_pass": computed_pass,
                "manual_verdict": MANUAL_VERDICTS.get(source["stage"], ""),
            }
        )
    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = pd.concat([_canonicalize(source) for source in SOURCES], ignore_index=True, sort=False)
    inventory.to_csv(INVENTORY_PATH, index=False)

    non_official = inventory[~inventory["is_official_reference"].fillna(False)].copy()
    published_pass_flags = _bool_series(non_official["published_pass"])
    computed_pass_flags = _bool_series(non_official["computed_account_level_pass"])
    passing = non_official[published_pass_flags | computed_pass_flags].copy()
    passing["promotion_blocker"] = passing["manual_verdict"]
    passing.to_csv(PASSING_PATH, index=False)

    route_summary = (
        non_official.groupby(["route_bucket", "engine_level"], dropna=False)
        .agg(
            candidate_count=("version", "count"),
            pass_count=("computed_account_level_pass", "sum"),
            published_pass_count=("published_pass", lambda s: int(_bool_series(pd.Series(s)).sum())),
            best_min_retention=("min_return_retention_ratio", "max"),
            best_worst_drawdown=("worst_drawdown_pct", "max"),
            best_max_days_below=("max_days_below_initial", "min"),
            best_max_consecutive_below=("max_consecutive_below_initial_days", "min"),
        )
        .reset_index()
    )

    true_engine_promoted = non_official[
        non_official["engine_level"].eq("true_engine")
        & (computed_pass_flags | published_pass_flags)
    ]
    decision_text = "stage085_cash_account_overlay_closed_no_promotion_switch_to_structural_sleeve_or_true_exposure_attribution"
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision_text,
        "candidate_rows": int(len(non_official)),
        "passing_rows": int(len(passing)),
        "true_engine_passing_rows": int(len(true_engine_promoted)),
        "route_summary": route_summary.to_dict(orient="records"),
        "key_reason": [
            "Stage074 proxy passed but Stage075 true engine failed the new target.",
            "Stage077-084 cash yield/fund basket rows are account-level overlays, not C9 signal/position alpha.",
            "Stage084 independent review found no statistics bug, but the pass is thin and not promotion-worthy.",
            "Continuing to change funds, basket size, cash threshold or pass line would be parameter rescue.",
        ],
        "next_route": [
            "Do not promote cash/account overlays into official strategy.",
            "If cash is still needed, treat it as real account liquidity/channel validation, not strategy result.",
            "For strategy improvement, switch to structural diversifier or true position/exposure attribution.",
        ],
        "overfit_start_reflection": "否。Stage085只汇总冻结结果并收束路线，不新增参数或按坏窗口救参。",
        "continue_value_start_reflection": "有。收束弱路线能防止继续在现金展示层消耗时间，并把下一轮实验转到结构性收益来源。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    focus_cols = [
        "stage",
        "source_type",
        "engine_level",
        "variant_label",
        "min_return_retention_ratio",
        "worst_drawdown_pct",
        "max_days_below_initial",
        "max_consecutive_below_initial_days",
        "published_pass",
        "computed_account_level_pass",
        "manual_verdict",
    ]
    report_lines = [
        "# Stage085 cash/account overlay route closure audit",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision_text}`。",
        "- 本阶段不回测、不改策略、不连接 CTP、不触发订单 API；只汇总 Stage073-084 的冻结结果。",
        "- 账户/现金/储备金路线没有可晋级版本：唯一真实引擎 Stage075 未通过；货基/现金收益系列只是账户层弱证据，且 Stage084 已经贴线。",
        "- 下一步应停止换基金、换篮子大小、调补款频率/比例或调通过门槛，转向结构性独立收益腿或真实持仓/成交暴露归因。",
        "",
        "## Route Summary",
        "",
        _md_table(route_summary),
        "",
        "## Passing But Not Promoted",
        "",
        _md_table(passing[[col for col in focus_cols if col in passing.columns]], max_rows=60),
        "",
        "## 过拟合与继续价值",
        "",
        "- 运行前过拟合反思：否。只读汇总冻结结果，不根据 2022/2023 或某个起点调参数。",
        "- 运行后过拟合反思：否。结论是停止现金/account overlay 救参；若继续调基金或阈值才会过拟合。",
        "- 继续价值：有，但不是继续现金路线；下一步应做结构性 sleeve 或真实暴露归因。",
        "",
        "## 输出",
        "",
        f"- inventory：`{INVENTORY_PATH}`",
        f"- passing：`{PASSING_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage085_cash_overlay_route_closure_audit.md"
    stage_lines = [
        "# Stage085 cash/account overlay route closure audit",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now():%Y-%m-%dT%H:%M:%S}",
        "- 阶段性质：Stage073-084 账户/现金/储备金路线只读收束审计",
        "- 是否重要突破：否，路线收束；不晋级",
        "- 是否触发A/B：否，本阶段不提出接入正式版候选",
        "",
        "## 外部调研与判断",
        "",
        "- 本轮外部调研结论沿用 Stage083/084：货基和基金回测需要显式处理 T+n、到账、限额、节假日和渠道约束；趋势系统的水下期更适合靠结构分散、波动率/资金治理和独立收益腿改善。",
        "- 本阶段判断：现金收益可以改善账户体验，但不能当成 C9 交易 alpha；贴线通过的账户层 proxy 不应晋级。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 新增参数：无交易参数。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        _md_table(route_summary),
        "",
        "## 通过但不晋级的行",
        "",
        _md_table(passing[[col for col in focus_cols if col in passing.columns]], max_rows=60),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision_text}`。",
        f"- 汇总候选行：`{len(non_official)}`；账户层通过行：`{len(passing)}`；真实引擎通过行：`{len(true_engine_promoted)}`。",
        "- 关键判断：Stage074 proxy 的通过已经被 Stage075 true engine 否定；Stage077-084 是现金收益/货基储备账户层，不改变 C9 信号和持仓 alpha；Stage084 独立审查确认无统计 bug 但边际过线，不适合晋级。",
        "- 下一步：停止现金/account overlay 救参；若仍关心实盘资金体验，单独做真实渠道申赎/流动性验收；若继续策略目标，应转向结构性独立收益腿或真实暴露归因。",
        "",
        "## 回测记录字段",
        "",
        "- 期末权益/总收益/最大回撤/Sharpe/滑点/交易次数/胜率：本阶段不新增回测，只汇总既有 Stage073-084 结果；详见 inventory 和各原 stage。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前：否。只读汇总冻结结果，不新增阈值或按窗口救参。",
        "- 运行后：否。结论是收束现金路线；继续换基金、篮子大小、补款频率或通过门槛才会过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前：有。必须先把弱路线收束，避免继续在账户展示层消耗时间。",
        "- 运行后：有，但方向切换。现金路线不值得继续作为策略晋级方向；结构性 sleeve/真实暴露归因仍值得做。",
        "",
        "## 输出",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- inventory：`{INVENTORY_PATH}`",
        f"- passing：`{PASSING_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")


if __name__ == "__main__":
    main()
